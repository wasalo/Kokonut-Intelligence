// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

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
        registry = new KokonutGuildRegistry(admin, admin);
        domains = new KokonutGuildDomain(admin, admin, registry);
        tasks = new KokonutTaskBoard(admin, admin, domains);
        reviews = new KokonutEvidenceReview(admin, admin, tasks);
        governance = new KokonutGuildGovernance(admin, admin);

        vm.startPrank(admin);
        registry.grantRole(registry.GUILD_ADMIN_ROLE(), admin);
        domains.grantRole(domains.DOMAIN_ADMIN_ROLE(), admin);
        tasks.grantRole(tasks.TASK_ADMIN_ROLE(), admin);
        reviews.grantRole(reviews.REVIEWER_ROLE(), admin);
        governance.grantRole(governance.PROPOSER_ROLE(), admin);
        governance.grantRole(governance.OBJECTOR_ROLE(), admin);
        governance.grantRole(governance.EXECUTOR_ROLE(), admin);
        registry.createGuild(guildId, guildKey, "Technology Guild", "ipfs://technology", admin);
        domainId = domains.createDomain(guildId, 0, "MRV", "ipfs://mrv");
        tasks.setEvidenceReview(address(reviews));
        tasks.grantRole(tasks.TASK_ADMIN_ROLE(), address(governance));
        domains.grantRole(domains.DOMAIN_ADMIN_ROLE(), address(governance));
        governance.setTargetAllowed(address(tasks), true);
        governance.setTargetSelectorAllowed(address(tasks), tasks.cancelTask.selector, true);
        governance.setTargetSelectorAllowed(address(tasks), tasks.markPaid.selector, true);
        governance.setGuildScopedTarget(address(tasks), true);
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

    function test_unregistered_guild_cannot_create_domain() public {
        vm.prank(admin);
        vm.expectRevert(KokonutGuildDomain.InvalidDomain.selector);
        domains.createDomain(keccak256("unregistered"), 0, "Invalid", "ipfs://invalid");
    }

    function test_default_admin_cannot_reacquire_operational_roles() public {
        address roleAdmin = address(0x998);
        KokonutGuildRegistry isolated = new KokonutGuildRegistry(admin, roleAdmin);
        bytes32 guildAdminRole = isolated.GUILD_ADMIN_ROLE();
        bytes32 roleAdminRole = isolated.ROLE_ADMIN_ROLE();
        assertFalse(isolated.hasRole(roleAdminRole, admin));
        assertEq(isolated.getRoleAdmin(guildAdminRole), roleAdminRole);

        vm.prank(admin);
        vm.expectRevert();
        isolated.grantRole(guildAdminRole, admin);

        vm.prank(roleAdmin);
        isolated.grantRole(guildAdminRole, admin);
        assertTrue(isolated.hasRole(guildAdminRole, admin));
    }

    function test_domain_deprecation_requires_steward_approval() public {
        vm.prank(admin);
        domains.setStatus(domainId, KokonutGuildDomain.DomainStatus.Deprecated);
        assertTrue(domains.deprecationRequested(domainId));

        vm.prank(address(0x999));
        vm.expectRevert();
        domains.approveDeprecation(domainId);

        vm.prank(admin);
        domains.approveDeprecation(domainId);
        assertEq(uint8(domains.getDomain(domainId).status), uint8(KokonutGuildDomain.DomainStatus.Deprecated));
    }

    function test_assigned_task_can_be_expired_without_task_admin() public {
        uint256 taskId = _createAssignedTask();
        vm.warp(block.timestamp + 7 days + 1);

        vm.prank(address(0x999));
        tasks.expireTask(taskId);
        assertEq(uint8(tasks.getTask(taskId).status), uint8(KokonutTaskBoard.TaskStatus.Cancelled));
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

    function test_guild_pause_blocks_existing_domain_task_activity() public {
        uint256 taskId = _createAssignedTask();
        vm.prank(admin);
        registry.setStatus(guildId, KokonutGuildRegistry.GuildStatus.Paused);

        vm.prank(contributor);
        vm.expectRevert(KokonutTaskBoard.UnauthorizedContributor.selector);
        tasks.submitEvidence(taskId, keccak256("late-evidence"));
    }

    function test_late_evidence_submission_is_rejected() public {
        uint256 taskId = _createAssignedTask();
        vm.warp(block.timestamp + 8 days);
        vm.prank(contributor);
        vm.expectRevert(KokonutTaskBoard.UnauthorizedContributor.selector);
        tasks.submitEvidence(taskId, keccak256("late-evidence"));
    }

    function test_revoking_review_prevents_payment() public {
        uint256 taskId = _createAssignedTask();
        bytes32 evidenceHash = keccak256("revoked-evidence");
        vm.prank(contributor);
        tasks.submitEvidence(taskId, evidenceHash);
        bytes32 reviewId = keccak256("review-revoke");
        vm.prank(admin);
        reviews.reviewEvidence(
            reviewId, taskId, KokonutEvidenceReview.ReviewDecision.Accepted, evidenceHash, keccak256("notes")
        );
        vm.prank(admin);
        reviews.revokeReview(reviewId, keccak256("invalidated"));

        vm.prank(admin);
        vm.expectRevert(abi.encodeWithSelector(KokonutTaskBoard.InvalidStatus.selector, taskId));
        tasks.markPaid(taskId, keccak256("payment"));

        vm.prank(admin);
        reviews.reviewEvidence(
            keccak256("review-replacement"),
            taskId,
            KokonutEvidenceReview.ReviewDecision.Rejected,
            evidenceHash,
            keccak256("replacement-notes")
        );
        assertEq(uint8(tasks.getTask(taskId).status), uint8(KokonutTaskBoard.TaskStatus.Rejected));
    }

    function test_review_and_payment_deadlines_are_enforced() public {
        uint256 taskId = _createAssignedTask();
        bytes32 evidenceHash = keccak256("deadline-evidence");
        vm.prank(contributor);
        tasks.submitEvidence(taskId, evidenceHash);

        vm.warp(block.timestamp + 7 days + tasks.REVIEW_GRACE_PERIOD() + 1);
        vm.prank(admin);
        vm.expectRevert(KokonutEvidenceReview.InvalidReview.selector);
        reviews.reviewEvidence(
            keccak256("late-review"), taskId, KokonutEvidenceReview.ReviewDecision.Accepted, evidenceHash, bytes32(0)
        );
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

    function test_governance_rechecks_selector_permission_before_execution() public {
        uint256 taskId = _createAssignedTask();
        bytes memory action = abi.encodeCall(KokonutTaskBoard.cancelTask, (taskId, keccak256("governance")));

        vm.prank(admin);
        uint256 motionId = governance.createMotion(guildId, address(tasks), action, uint64(block.timestamp + 1 days));
        vm.warp(block.timestamp + 1 days + 1);
        vm.prank(admin);
        governance.finalizeMotion(motionId);

        vm.prank(admin);
        governance.setTargetSelectorAllowed(address(tasks), tasks.cancelTask.selector, false);
        vm.prank(admin);
        vm.expectRevert(abi.encodeWithSelector(KokonutGuildGovernance.TargetNotAllowed.selector, address(tasks)));
        governance.executeMotion(motionId);
    }

    function test_governance_rejects_cross_guild_task_motion() public {
        bytes32 otherGuildId = keccak256("impact");
        vm.prank(admin);
        registry.createGuild(otherGuildId, keccak256("impact-key"), "Impact Guild", "ipfs://impact", admin);
        uint256 otherDomainId;
        vm.prank(admin);
        otherDomainId = domains.createDomain(otherGuildId, 0, "MRV", "ipfs://impact-mrv");
        uint256 otherTaskId;
        vm.prank(admin);
        otherTaskId = tasks.createTask(
            otherDomainId,
            keccak256("other-task"),
            "ipfs://other-task",
            0,
            address(0),
            uint64(block.timestamp + 7 days),
            keccak256("evidence")
        );
        bytes memory action = abi.encodeCall(KokonutTaskBoard.cancelTask, (otherTaskId, keccak256("cross-guild")));
        vm.prank(admin);
        vm.expectRevert(KokonutGuildGovernance.InvalidMotion.selector);
        governance.createMotion(guildId, address(tasks), action, uint64(block.timestamp + 1 days));
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
