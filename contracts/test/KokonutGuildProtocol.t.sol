// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {Test} from "forge-std/Test.sol";
import {KokonutEvidenceReview} from "../src/KokonutEvidenceReview.sol";
import {KokonutGuildDomain} from "../src/KokonutGuildDomain.sol";
import {KokonutGuildGovernance} from "../src/KokonutGuildGovernance.sol";
import {KokonutGuildRegistry} from "../src/KokonutGuildRegistry.sol";
import {KokonutTaskBoard} from "../src/KokonutTaskBoard.sol";

contract KokonutGuildProtocolTest is Test {
    KokonutGuildRegistry internal registry;
    KokonutGuildDomain internal domains;
    KokonutTaskBoard internal tasks;
    KokonutEvidenceReview internal reviews;
    KokonutGuildGovernance internal governance;

    address internal admin = address(0x100);
    address internal contributor = address(0x200);
    bytes32 internal guildId = keccak256("technology");
    bytes32 internal guildKey = keccak256("technology-key");
    uint256 internal domainId;

    function setUp() public {
        registry = new KokonutGuildRegistry(admin);
        domains = new KokonutGuildDomain(admin, registry);
        tasks = new KokonutTaskBoard(admin, domains);
        reviews = new KokonutEvidenceReview(admin, tasks);
        governance = new KokonutGuildGovernance(admin);

        vm.startPrank(admin);
        registry.createGuild(guildId, guildKey, "Technology Guild", "ipfs://technology", admin);
        domainId = domains.createDomain(guildId, 0, "MRV", "ipfs://mrv");
        tasks.setEvidenceReview(address(reviews));
        tasks.grantRole(tasks.TASK_ADMIN_ROLE(), address(governance));
        governance.setTargetAllowed(address(tasks), true);
        vm.stopPrank();
    }

    function test_guild_domain_task_review_vertical_slice() public {
        uint256 taskId = _createAssignedTask();
        bytes32 evidenceHash = keccak256("field-evidence");

        vm.prank(contributor);
        tasks.submitEvidence(taskId, evidenceHash);

        bytes32 reviewId = keccak256("review-1");
        vm.prank(admin);
        reviews.reviewEvidence(
            reviewId, taskId, KokonutEvidenceReview.ReviewDecision.Accepted, evidenceHash, keccak256("review-notes")
        );

        KokonutTaskBoard.Task memory task = tasks.getTask(taskId);
        assertEq(task.guildId, guildId);
        assertEq(task.domainId, domainId);
        assertEq(task.contributor, contributor);
        assertEq(uint8(task.status), uint8(KokonutTaskBoard.TaskStatus.Accepted));
        assertEq(uint8(reviews.getReview(reviewId).status), uint8(KokonutEvidenceReview.ReviewStatus.Accepted));
    }

    function test_review_can_be_disputed_and_resolved() public {
        uint256 taskId = _createAssignedTask();
        bytes32 evidenceHash = keccak256("disputed-evidence");
        vm.prank(contributor);
        tasks.submitEvidence(taskId, evidenceHash);

        bytes32 reviewId = keccak256("review-2");
        vm.prank(admin);
        reviews.reviewEvidence(
            reviewId, taskId, KokonutEvidenceReview.ReviewDecision.Accepted, evidenceHash, keccak256("notes")
        );

        vm.prank(contributor);
        reviews.disputeReview(reviewId, keccak256("missing evidence"));
        assertEq(uint8(tasks.getTask(taskId).status), uint8(KokonutTaskBoard.TaskStatus.Disputed));

        vm.prank(admin);
        reviews.resolveDispute(reviewId, true, keccak256("resolved"));
        assertEq(uint8(tasks.getTask(taskId).status), uint8(KokonutTaskBoard.TaskStatus.Accepted));
    }

    function test_governance_motion_executes_only_after_unopposed_window() public {
        uint256 taskId = _createAssignedTask();
        bytes memory action = abi.encodeCall(KokonutTaskBoard.cancelTask, (taskId, keccak256("governance")));

        vm.prank(admin);
        uint256 motionId = governance.createMotion(guildId, address(tasks), action, uint64(block.timestamp + 1 days));

        vm.prank(admin);
        vm.expectRevert(abi.encodeWithSelector(KokonutGuildGovernance.ObjectionWindowOpen.selector, motionId));
        governance.finalizeMotion(motionId);

        vm.warp(block.timestamp + 1 days + 1);
        vm.prank(admin);
        governance.finalizeMotion(motionId);
        vm.prank(admin);
        governance.executeMotion(motionId);

        assertEq(uint8(tasks.getTask(taskId).status), uint8(KokonutTaskBoard.TaskStatus.Cancelled));
        assertEq(uint8(governance.getMotion(motionId).status), uint8(KokonutGuildGovernance.MotionStatus.Executed));
    }

    function test_governance_objection_rejects_motion() public {
        uint256 taskId = _createAssignedTask();
        bytes memory action = abi.encodeCall(KokonutTaskBoard.cancelTask, (taskId, keccak256("governance")));

        vm.prank(admin);
        uint256 motionId = governance.createMotion(guildId, address(tasks), action, uint64(block.timestamp + 1 days));
        vm.prank(admin);
        governance.objectMotion(motionId, keccak256("needs community review"));
        vm.warp(block.timestamp + 1 days + 1);
        vm.prank(admin);
        governance.finalizeMotion(motionId);

        assertEq(uint8(governance.getMotion(motionId).status), uint8(KokonutGuildGovernance.MotionStatus.Rejected));
        assertEq(uint8(tasks.getTask(taskId).status), uint8(KokonutTaskBoard.TaskStatus.Assigned));
    }

    function _createAssignedTask() internal returns (uint256 taskId) {
        vm.prank(admin);
        taskId = tasks.createTask(
            domainId,
            keccak256(abi.encode("task", block.timestamp, taskId)),
            "ipfs://task",
            0,
            address(0),
            uint64(block.timestamp + 7 days),
            keccak256("evidence-requirement")
        );
        vm.prank(admin);
        tasks.assignTask(taskId, contributor);
    }
}
