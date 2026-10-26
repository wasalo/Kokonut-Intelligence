// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {KokonutCreditToken} from "../src/KokonutCreditToken.sol";
import {ERC1155Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC1155/ERC1155Upgradeable.sol";
import {IAccessControl} from "@openzeppelin/contracts/access/IAccessControl.sol";

contract KokonutCreditTokenTest is Test {
    KokonutCreditToken public token;
    address public admin = makeAddr("admin");
    address public issuer = makeAddr("issuer");
    address public burner = makeAddr("burner");
    address public pauser = makeAddr("pauser");
    address public upgrader = makeAddr("upgrader");
    address public user = makeAddr("user");

    bytes32 constant BATCH_ID = keccak256("batch-2026-adelphi");
    bytes32 constant EVIDENCE_HASH = keccak256("evidence-001");
    uint256 constant NEXT_SERIAL_NUMBER_MAPPING_SLOT = 5;

    function setUp() public {
        KokonutCreditToken implementation = new KokonutCreditToken();
        bytes memory initialization = abi.encodeCall(
            KokonutCreditToken.initialize,
            (admin, issuer, burner, pauser, upgrader, "https://api.kokonut.network/credit-tokens/{id}.json")
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(implementation), initialization);
        token = KokonutCreditToken(address(proxy));

        vm.startPrank(admin);
        token.grantRole(token.BURNER_ROLE(), user);
        vm.stopPrank();
    }

    function testInitialize() public view {
        assertTrue(token.hasRole(token.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(token.hasRole(token.ISSUER_ROLE(), issuer));
        assertTrue(token.hasRole(token.BURNER_ROLE(), burner));
        assertTrue(token.hasRole(token.PAUSER_ROLE(), pauser));
        assertTrue(token.hasRole(token.UPGRADER_ROLE(), upgrader));
    }

    function testIssue() public {
        vm.prank(issuer);
        uint256 tokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 0)));
        token.issue(BATCH_ID, user, 100, 2026, "KE", "IPCC 2006 Tier 2", EVIDENCE_HASH);

        assertEq(token.balanceOf(user, tokenId), 100);
        assertEq(token.totalIssued(tokenId), 100);
        assertEq(token.totalRetired(tokenId), 0);
        assertTrue(token.batchExists(BATCH_ID));

        KokonutCreditToken.CreditRecord memory info = token.getCreditInfo(tokenId);
        assertEq(info.batchId, BATCH_ID);
        assertEq(info.vintageYear, 2026);
        assertEq(info.jurisdiction, "KE");
        assertEq(info.methodology, "IPCC 2006 Tier 2");
        assertEq(info.evidenceHash, EVIDENCE_HASH);
    }

    function testRepeatedIssuanceGetsDistinctSerialsForSameRecipient() public {
        vm.startPrank(issuer);
        token.issue(BATCH_ID, user, 100, 2026, "KE", "IPCC 2006 Tier 2", EVIDENCE_HASH);
        token.issue(BATCH_ID, user, 25, 2026, "KE", "IPCC 2006 Tier 2", keccak256("evidence-002"));
        vm.stopPrank();

        uint256 firstTokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 0)));
        uint256 secondTokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 1)));

        assertEq(token.balanceOf(user, firstTokenId), 100);
        assertEq(token.balanceOf(user, secondTokenId), 25);
        assertEq(token.totalIssued(firstTokenId) + token.totalIssued(secondTokenId), 125);
        assertEq(token.getCreditInfo(firstTokenId).serialNumber, 0);
        assertEq(token.getCreditInfo(secondTokenId).serialNumber, 1);
    }

    function testRepeatedBatchIssueGetsDistinctSerialsForSameRecipient() public {
        KokonutCreditToken.IssueParams[] memory params = new KokonutCreditToken.IssueParams[](2);
        params[0] = KokonutCreditToken.IssueParams({
            batchId: BATCH_ID,
            recipient: user,
            amount: 11,
            vintageYear: 2026,
            jurisdiction: "KE",
            methodology: "IPCC",
            evidenceHash: keccak256("batch-evidence-001")
        });
        params[1] = KokonutCreditToken.IssueParams({
            batchId: BATCH_ID,
            recipient: user,
            amount: 13,
            vintageYear: 2026,
            jurisdiction: "KE",
            methodology: "IPCC",
            evidenceHash: keccak256("batch-evidence-002")
        });

        vm.prank(issuer);
        token.batchIssue(params);

        uint256 firstTokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 0)));
        uint256 secondTokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 1)));
        assertEq(token.balanceOf(user, firstTokenId), 11);
        assertEq(token.balanceOf(user, secondTokenId), 13);
    }

    function testIssuanceSkipsExistingSerialZeroWhenCounterIsUninitialized() public {
        vm.prank(issuer);
        token.issue(BATCH_ID, user, 10, 2026, "KE", "IPCC", EVIDENCE_HASH);

        bytes32 batchVintageKey = keccak256(abi.encode(BATCH_ID, uint256(2026)));
        bytes32 counterSlot = keccak256(abi.encode(batchVintageKey, NEXT_SERIAL_NUMBER_MAPPING_SLOT));
        // Simulate the appended mapping's default state after upgrading a proxy
        // that already contains an original serial-zero record.
        vm.store(address(token), counterSlot, bytes32(0));

        vm.prank(issuer);
        token.issue(BATCH_ID, user, 7, 2026, "KE", "IPCC", keccak256("post-upgrade"));

        uint256 firstTokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 0)));
        uint256 secondTokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 1)));
        assertEq(token.balanceOf(user, firstTokenId), 10);
        assertEq(token.balanceOf(user, secondTokenId), 7);
    }

    function testFuzz_SequentialIssuancePreservesEachCreditAmount(uint96 firstAmount, uint96 secondAmount) public {
        firstAmount = uint96(bound(firstAmount, 1, type(uint96).max));
        secondAmount = uint96(bound(secondAmount, 1, type(uint96).max));

        vm.startPrank(issuer);
        token.issue(BATCH_ID, user, firstAmount, 2026, "KE", "IPCC", EVIDENCE_HASH);
        token.issue(BATCH_ID, user, secondAmount, 2026, "KE", "IPCC", keccak256("fuzz-evidence"));
        vm.stopPrank();

        uint256 firstTokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 0)));
        uint256 secondTokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 1)));
        assertEq(token.balanceOf(user, firstTokenId), firstAmount);
        assertEq(token.balanceOf(user, secondTokenId), secondAmount);
        assertEq(
            token.totalIssued(firstTokenId) + token.totalIssued(secondTokenId),
            uint256(firstAmount) + uint256(secondAmount)
        );
    }

    function testIssueRejectsZeroBatchIdentity() public {
        vm.prank(issuer);
        vm.expectRevert(KokonutCreditToken.InvalidCreditData.selector);
        token.issue(bytes32(0), user, 1, 2026, "KE", "IPCC", EVIDENCE_HASH);
    }

    function testIssueRevertsOnZeroAddress() public {
        vm.prank(issuer);
        vm.expectRevert(KokonutCreditToken.ZeroAddress.selector);
        token.issue(BATCH_ID, address(0), 100, 2026, "KE", "IPCC", EVIDENCE_HASH);
    }

    function testIssueRevertsOnZeroAmount() public {
        vm.prank(issuer);
        vm.expectRevert(KokonutCreditToken.ZeroAmount.selector);
        token.issue(BATCH_ID, user, 0, 2026, "KE", "IPCC", EVIDENCE_HASH);
    }

    function testIssueRevertsOnUnauthorized() public {
        vm.prank(user);
        vm.expectRevert();
        token.issue(BATCH_ID, user, 100, 2026, "KE", "IPCC", EVIDENCE_HASH);
    }

    function testRetire() public {
        vm.startPrank(issuer);
        token.issue(BATCH_ID, user, 100, 2026, "KE", "IPCC", EVIDENCE_HASH);
        vm.stopPrank();

        uint256 tokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 0)));
        vm.prank(user);
        token.retire(tokenId, 50, keccak256("voluntary retirement"));

        assertEq(token.balanceOf(user, tokenId), 50);
        assertEq(token.totalRetired(tokenId), 50);
        assertFalse(token.isRetired(tokenId));
    }

    function testRetireFullBalance() public {
        vm.startPrank(issuer);
        token.issue(BATCH_ID, user, 100, 2026, "KE", "IPCC", EVIDENCE_HASH);
        vm.stopPrank();

        uint256 tokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 0)));
        vm.prank(user);
        token.retire(tokenId, 100, keccak256("full retirement"));

        assertEq(token.balanceOf(user, tokenId), 0);
        assertTrue(token.isRetired(tokenId));
    }

    function testRetireRevertsOnInsufficientBalance() public {
        vm.startPrank(issuer);
        token.issue(BATCH_ID, user, 100, 2026, "KE", "IPCC", EVIDENCE_HASH);
        vm.stopPrank();

        uint256 tokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 0)));
        vm.prank(user);
        vm.expectRevert();
        token.retire(tokenId, 150, keccak256("over-retirement"));
    }

    function testNonTransferable() public {
        vm.startPrank(issuer);
        token.issue(BATCH_ID, user, 100, 2026, "KE", "IPCC", EVIDENCE_HASH);
        vm.stopPrank();

        uint256 tokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 0)));
        address recipient = makeAddr("recipient");

        vm.prank(user);
        vm.expectRevert(KokonutCreditToken.NonTransferable.selector);
        token.safeTransferFrom(user, recipient, tokenId, 10, "");

        vm.prank(user);
        vm.expectRevert(KokonutCreditToken.NonTransferable.selector);
        token.setApprovalForAll(recipient, true);
    }

    function testPause() public {
        vm.prank(pauser);
        token.pause();

        vm.prank(issuer);
        vm.expectRevert();
        token.issue(BATCH_ID, user, 100, 2026, "KE", "IPCC", EVIDENCE_HASH);

        vm.prank(pauser);
        token.unpause();

        vm.prank(issuer);
        token.issue(BATCH_ID, user, 100, 2026, "KE", "IPCC", EVIDENCE_HASH);
    }

    function testAvailableBalance() public {
        vm.startPrank(issuer);
        token.issue(BATCH_ID, user, 100, 2026, "KE", "IPCC", EVIDENCE_HASH);
        vm.stopPrank();

        uint256 tokenId = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 0)));
        assertEq(token.availableBalance(tokenId), 100);

        vm.prank(user);
        token.retire(tokenId, 30, keccak256("partial"));
        assertEq(token.availableBalance(tokenId), 70);
    }

    function testBatchIssue() public {
        KokonutCreditToken.IssueParams[] memory params = new KokonutCreditToken.IssueParams[](2);
        params[0] = KokonutCreditToken.IssueParams({
            batchId: BATCH_ID,
            recipient: user,
            amount: 100,
            vintageYear: 2026,
            jurisdiction: "KE",
            methodology: "IPCC 2006 Tier 2",
            evidenceHash: keccak256("ev1")
        });
        params[1] = KokonutCreditToken.IssueParams({
            batchId: keccak256("batch-2026-other"),
            recipient: makeAddr("user2"),
            amount: 200,
            vintageYear: 2026,
            jurisdiction: "TZ",
            methodology: "IPCC 2006 Tier 2",
            evidenceHash: keccak256("ev2")
        });

        vm.prank(issuer);
        token.batchIssue(params);

        uint256 tokenId0 = uint256(keccak256(abi.encode(BATCH_ID, 2026, user, 0)));
        uint256 tokenId1 = uint256(keccak256(abi.encode(params[1].batchId, 2026, params[1].recipient, 0)));
        assertEq(token.balanceOf(user, tokenId0), 100);
        assertEq(token.balanceOf(params[1].recipient, tokenId1), 200);
    }
}
