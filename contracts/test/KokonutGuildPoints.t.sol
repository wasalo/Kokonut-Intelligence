// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {KokonutGuildPoints} from "../src/KokonutGuildPoints.sol";
import {KokonutGuildDomain} from "../src/KokonutGuildDomain.sol";
import {KokonutGuildRegistry} from "../src/KokonutGuildRegistry.sol";

contract KokonutGuildPointsV2 is KokonutGuildPoints {
    function version() external pure returns (uint256) {
        return 2;
    }
}

contract KokonutGuildPointsTest is Test {
    KokonutGuildPoints internal points;
    KokonutGuildDomain internal domains;
    address internal admin = address(0x100);
    address internal awarder = address(0x101);
    address internal signer;
    address internal reverser = address(0x103);
    address internal pauser = address(0x104);
    address internal upgrader = address(0x105);
    address internal contributor = address(0x200);
    uint256 internal signerKey = 0xBEEF;

    bytes32 internal guildId = keccak256("technology");
    uint256 internal domainId = 1;
    bytes32 internal evidenceHash = keccak256("evidence");
    bytes32 internal ledgerRecordHash = keccak256("ledger-record");
    bytes32 internal calculationVersion = keccak256("v2026.07");

    function setUp() public {
        signer = vm.addr(signerKey);
        KokonutGuildRegistry registry = new KokonutGuildRegistry(admin);
        domains = new KokonutGuildDomain(admin, registry);
        vm.startPrank(admin);
        registry.createGuild(guildId, keccak256("technology-key"), "Technology", "ipfs://technology", admin);
        domains.createDomain(guildId, 0, "MRV", "ipfs://mrv");
        vm.stopPrank();
        KokonutGuildPoints implementation = new KokonutGuildPoints();
        bytes memory initialization = abi.encodeCall(
            KokonutGuildPoints.initialize,
            (admin, awarder, signer, reverser, pauser, upgrader, domains, "ipfs://kgp/{id}.json")
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(implementation), initialization);
        points = KokonutGuildPoints(address(proxy));
    }

    function test_automatic_award_is_domain_scoped_and_idempotent() public {
        bytes32 awardId = keccak256("award-1");
        vm.prank(awarder);
        points.award(
            awardId, guildId, contributor, domainId, 125, 1, evidenceHash, ledgerRecordHash, calculationVersion
        );

        assertEq(points.balanceOf(contributor, domainId), 125);
        assertEq(points.balanceOf(contributor, 2), 0);
        assertEq(points.getAward(awardId).outstanding, 125);

        vm.prank(awarder);
        vm.expectRevert(abi.encodeWithSelector(KokonutGuildPoints.AwardAlreadySettled.selector, awardId));
        points.award(
            awardId, guildId, contributor, domainId, 125, 1, evidenceHash, ledgerRecordHash, calculationVersion
        );
    }

    function test_transfers_and_approvals_are_rejected() public {
        _award(50);

        vm.prank(contributor);
        vm.expectRevert(KokonutGuildPoints.NonTransferable.selector);
        points.safeTransferFrom(contributor, address(0x201), domainId, 1, "");

        vm.prank(contributor);
        vm.expectRevert(KokonutGuildPoints.NonTransferable.selector);
        points.setApprovalForAll(address(0x202), true);

        vm.prank(contributor);
        vm.expectRevert(KokonutGuildPoints.NonTransferable.selector);
        points.safeBatchTransferFrom(contributor, address(0x201), new uint256[](1), new uint256[](1), "");
    }

    function test_claim_voucher_mints_once_to_signed_contributor() public {
        KokonutGuildPoints.ClaimVoucher memory voucher = KokonutGuildPoints.ClaimVoucher({
            awardId: keccak256("claim-1"),
            guildId: guildId,
            contributor: contributor,
            domainId: domainId,
            amount: 80,
            epoch: 2,
            evidenceHash: evidenceHash,
            ledgerRecordHash: ledgerRecordHash,
            calculationVersion: calculationVersion,
            nonce: 7,
            deadline: uint48(block.timestamp + 1 days)
        });
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerKey, points.claimDigest(voucher));
        bytes memory signature = abi.encodePacked(r, s, v);

        vm.prank(contributor);
        points.claim(voucher, signature);

        assertEq(points.balanceOf(contributor, domainId), 80);
        assertTrue(points.usedClaimNonces(contributor, 7));

        vm.prank(contributor);
        vm.expectRevert(abi.encodeWithSelector(KokonutGuildPoints.ClaimNonceUsed.selector, contributor, 7));
        points.claim(voucher, signature);
    }

    function test_claim_rejects_wrong_sender_and_expired_voucher() public {
        KokonutGuildPoints.ClaimVoucher memory voucher = KokonutGuildPoints.ClaimVoucher({
            awardId: keccak256("claim-2"),
            guildId: guildId,
            contributor: contributor,
            domainId: domainId,
            amount: 10,
            epoch: 1,
            evidenceHash: evidenceHash,
            ledgerRecordHash: ledgerRecordHash,
            calculationVersion: calculationVersion,
            nonce: 8,
            deadline: uint48(block.timestamp)
        });
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerKey, points.claimDigest(voucher));

        vm.prank(address(0x201));
        vm.expectRevert(
            abi.encodeWithSelector(KokonutGuildPoints.ClaimSenderMismatch.selector, contributor, address(0x201))
        );
        points.claim(voucher, abi.encodePacked(r, s, v));

        vm.warp(block.timestamp + 1);
        vm.prank(contributor);
        vm.expectRevert(abi.encodeWithSelector(KokonutGuildPoints.ClaimExpired.selector, uint48(block.timestamp - 1)));
        points.claim(voucher, abi.encodePacked(r, s, v));
    }

    function test_reversal_is_append_only_and_cannot_exceed_outstanding() public {
        bytes32 awardId = _award(100);

        vm.prank(reverser);
        points.reverseAward(
            keccak256("reversal-1"), awardId, 30, keccak256("reason"), keccak256("correction"), calculationVersion
        );
        assertEq(points.balanceOf(contributor, domainId), 70);
        assertEq(points.getAward(awardId).outstanding, 70);

        vm.prank(reverser);
        vm.expectRevert(abi.encodeWithSelector(KokonutGuildPoints.ExcessiveReversal.selector, awardId, 71, 70));
        points.reverseAward(
            keccak256("reversal-2"), awardId, 71, keccak256("reason"), keccak256("correction"), calculationVersion
        );
    }

    function test_roles_pause_and_upgrade_are_enforced() public {
        vm.prank(address(0x999));
        vm.expectRevert();
        points.award(
            keccak256("unauthorized"),
            guildId,
            contributor,
            domainId,
            1,
            1,
            evidenceHash,
            ledgerRecordHash,
            calculationVersion
        );

        vm.prank(pauser);
        points.pause();
        vm.prank(awarder);
        vm.expectRevert();
        points.award(
            keccak256("paused"),
            guildId,
            contributor,
            domainId,
            1,
            1,
            evidenceHash,
            ledgerRecordHash,
            calculationVersion
        );
        vm.prank(pauser);
        points.unpause();

        _award(11);
        KokonutGuildPointsV2 implementation = new KokonutGuildPointsV2();
        vm.prank(upgrader);
        points.upgradeToAndCall(address(implementation), "");
        assertEq(KokonutGuildPointsV2(address(points)).version(), 2);
        assertEq(points.balanceOf(contributor, domainId), 11);
    }

    function test_admin_cannot_grant_or_use_upgrade_role() public {
        bytes32 upgraderRole = points.UPGRADER_ROLE();
        vm.prank(admin);
        vm.expectRevert();
        points.grantRole(upgraderRole, admin);

        KokonutGuildPointsV2 implementation = new KokonutGuildPointsV2();
        vm.prank(admin);
        vm.expectRevert();
        points.upgradeToAndCall(address(implementation), "");
    }

    function test_upgrade_preserves_reversal_state_and_roles() public {
        bytes32 awardId = _award(100);
        vm.prank(reverser);
        bytes32 reversalId = keccak256("upgrade-reversal");
        points.reverseAward(reversalId, awardId, 25, keccak256("reason"), ledgerRecordHash, calculationVersion);

        KokonutGuildPointsV2 implementation = new KokonutGuildPointsV2();
        vm.prank(upgrader);
        points.upgradeToAndCall(address(implementation), "");

        assertEq(points.balanceOf(contributor, domainId), 75);
        assertEq(points.getAward(awardId).outstanding, 75);
        assertTrue(points.settledReversals(reversalId));
        assertTrue(points.hasRole(points.AWARDER_ROLE(), awarder));
        assertTrue(points.hasRole(points.UPGRADER_ROLE(), upgrader));
    }

    function test_domain_registry_migration_is_one_time_and_upgrade_compatible() public {
        KokonutGuildRegistry registry = new KokonutGuildRegistry(admin);
        KokonutGuildDomain replacement = new KokonutGuildDomain(admin, registry);
        vm.startPrank(admin);
        registry.createGuild(guildId, keccak256("replacement-key"), "Replacement", "ipfs://replacement", admin);
        replacement.createDomain(guildId, 0, "Replacement MRV", "ipfs://replacement-mrv");
        vm.stopPrank();

        KokonutGuildPointsV2 implementation = new KokonutGuildPointsV2();
        bytes memory migration = abi.encodeCall(KokonutGuildPoints.reinitializeDomainRegistry, (replacement));
        vm.store(address(points), bytes32(uint256(3)), bytes32(0));
        vm.prank(upgrader);
        points.upgradeToAndCall(address(implementation), migration);
        assertEq(address(points.domainRegistry()), address(replacement));

        vm.prank(upgrader);
        vm.expectRevert();
        points.reinitializeDomainRegistry(replacement);
    }

    function _award(uint256 amount) internal returns (bytes32 awardId) {
        awardId = keccak256(abi.encode("award", amount, points.balanceOf(contributor, domainId)));
        vm.prank(awarder);
        points.award(
            awardId, guildId, contributor, domainId, amount, 1, evidenceHash, ledgerRecordHash, calculationVersion
        );
    }
}
