// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {KokonutGuildPoints} from "../src/KokonutGuildPoints.sol";
import {KokonutGuildPointsV2Harness} from "./KokonutGuildPointsV2Harness.sol";
import {KokonutGuildUpgradeTimelock} from "../src/KokonutGuildUpgradeTimelock.sol";
import {KokonutGuildDomain} from "../src/KokonutGuildDomain.sol";
import {KokonutGuildRegistry} from "../src/KokonutGuildRegistry.sol";

contract IncompatibleGuildImplementation {}

contract KokonutGuildUpgradeTimelockTest is Test {
    KokonutGuildPoints internal points;
    KokonutGuildDomain internal domains;
    KokonutGuildUpgradeTimelock internal timelock;
    address internal admin = address(0x100);
    address internal proposer = address(0x101);
    address internal executor = address(0x102);
    uint256 internal constant DELAY = 2 days;

    function setUp() public {
        KokonutGuildRegistry registry = new KokonutGuildRegistry(admin);
        domains = new KokonutGuildDomain(admin, registry);
        vm.startPrank(admin);
        registry.createGuild(bytes32("timelock"), bytes32("timelock-key"), "Timelock", "ipfs://timelock", admin);
        domains.createDomain(bytes32("timelock"), 0, "Operations", "ipfs://operations");
        vm.stopPrank();
        KokonutGuildPoints implementation = new KokonutGuildPoints();
        bytes memory init = abi.encodeCall(
            KokonutGuildPoints.initialize, (admin, admin, admin, admin, admin, admin, domains, "ipfs://kgp")
        );
        points = KokonutGuildPoints(address(new ERC1967Proxy(address(implementation), init)));
        timelock = new KokonutGuildUpgradeTimelock(admin, proposer, executor, DELAY, address(points));
        bytes32 upgraderRole = points.UPGRADER_ROLE();
        vm.prank(admin);
        points.grantRole(upgraderRole, address(timelock));
        vm.prank(admin);
        points.revokeRole(upgraderRole, admin);
    }

    function test_upgrade_requires_delay_and_executor() public {
        KokonutGuildPointsV2Harness nextImplementation = new KokonutGuildPointsV2Harness();
        vm.prank(proposer);
        bytes32 id = timelock.queueUpgrade(address(points), address(nextImplementation), "");

        vm.prank(executor);
        vm.expectRevert();
        timelock.executeUpgrade(id);

        vm.warp(block.timestamp + DELAY);
        vm.prank(address(0x999));
        vm.expectRevert();
        timelock.executeUpgrade(id);

        vm.prank(executor);
        timelock.executeUpgrade(id);
        assertEq(KokonutGuildPointsV2Harness(address(points)).version(), 2);
    }

    function test_roles_must_be_distinct() public {
        vm.expectRevert(KokonutGuildUpgradeTimelock.InvalidUpgrade.selector);
        new KokonutGuildUpgradeTimelock(admin, admin, executor, DELAY, address(points));
    }

    function test_rejects_unapproved_proxy() public {
        KokonutGuildPointsV2Harness implementation = new KokonutGuildPointsV2Harness();
        KokonutGuildPointsV2Harness wrongProxy = new KokonutGuildPointsV2Harness();
        vm.prank(proposer);
        vm.expectRevert(KokonutGuildUpgradeTimelock.InvalidUpgrade.selector);
        timelock.queueUpgrade(address(wrongProxy), address(implementation), "");
    }

    function test_rejects_incompatible_implementation() public {
        IncompatibleGuildImplementation implementation = new IncompatibleGuildImplementation();
        vm.prank(proposer);
        vm.expectRevert(KokonutGuildUpgradeTimelock.UpgradeCompatibilityFailed.selector);
        timelock.queueUpgrade(address(points), address(implementation), "");
    }

    function test_rejects_stale_queued_upgrade() public {
        KokonutGuildPointsV2Harness first = new KokonutGuildPointsV2Harness();
        KokonutGuildPointsV2Harness second = new KokonutGuildPointsV2Harness();
        vm.startPrank(proposer);
        bytes32 firstId = timelock.queueUpgrade(address(points), address(first), "");
        bytes32 secondId = timelock.queueUpgrade(address(points), address(second), "");
        vm.stopPrank();

        vm.warp(block.timestamp + DELAY);
        vm.prank(executor);
        timelock.executeUpgrade(firstId);
        vm.prank(executor);
        vm.expectRevert(KokonutGuildUpgradeTimelock.UpgradeCompatibilityFailed.selector);
        timelock.executeUpgrade(secondId);
    }
}
