// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {KokonutGuildDomain} from "./KokonutGuildDomain.sol";

/// @title Kokonut Task Board
/// @notice Tracks operational Guild tasks without moving treasury funds.
contract KokonutTaskBoard is AccessControl {
    bytes32 public constant TASK_ADMIN_ROLE = keccak256("TASK_ADMIN_ROLE");

    enum TaskStatus {
        Open,
        Assigned,
        Submitted,
        Accepted,
        Rejected,
        Disputed,
        Cancelled,
        Paid
    }

    struct Task {
        uint256 taskId;
        bytes32 guildId;
        uint256 domainId;
        bytes32 taskKey;
        address contributor;
        uint256 rewardAmount;
        address rewardToken;
        uint64 deadline;
        bytes32 evidenceRequirementHash;
        bytes32 submittedEvidenceHash;
        string metadataURI;
        TaskStatus status;
    }

    KokonutGuildDomain public immutable domains;
    address public evidenceReview;
    uint256 public nextTaskId = 1;
    mapping(uint256 taskId => Task task) private _tasks;
    mapping(bytes32 taskKey => uint256 taskId) public taskIdByKey;

    error InvalidTask();
    error InvalidEvidenceReview();
    error UnknownTask(uint256 taskId);
    error TaskKeyExists(bytes32 taskKey);
    error TaskNotAssignable(uint256 taskId);
    error UnauthorizedContributor();
    error InvalidStatus(uint256 taskId);
    error OnlyEvidenceReview();

    event TaskCreated(uint256 indexed taskId, bytes32 indexed guildId, uint256 indexed domainId, bytes32 taskKey);
    event TaskAssigned(uint256 indexed taskId, address indexed contributor);
    event TaskEvidenceSubmitted(uint256 indexed taskId, address indexed contributor, bytes32 evidenceHash);
    event TaskStatusUpdated(uint256 indexed taskId, TaskStatus status, bytes32 referenceHash);
    event EvidenceReviewUpdated(address indexed review);

    constructor(address admin, KokonutGuildDomain guildDomains) {
        if (admin == address(0) || address(guildDomains) == address(0)) revert InvalidTask();
        domains = guildDomains;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(TASK_ADMIN_ROLE, admin);
    }

    function setEvidenceReview(address review) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (review == address(0)) revert InvalidEvidenceReview();
        evidenceReview = review;
        emit EvidenceReviewUpdated(review);
    }

    function createTask(
        uint256 domainId,
        bytes32 taskKey,
        string calldata metadataURI,
        uint256 rewardAmount,
        address rewardToken,
        uint64 deadline,
        bytes32 evidenceRequirementHash
    ) external onlyRole(TASK_ADMIN_ROLE) returns (uint256 taskId) {
        if (!domains.isActiveDomain(domainId) || taskKey == bytes32(0) || deadline <= block.timestamp) revert InvalidTask();
        if (taskIdByKey[taskKey] != 0) revert TaskKeyExists(taskKey);

        taskId = nextTaskId++;
        bytes32 guildId = domains.guildIdOf(domainId);
        _tasks[taskId] = Task(
            taskId,
            guildId,
            domainId,
            taskKey,
            address(0),
            rewardAmount,
            rewardToken,
            deadline,
            evidenceRequirementHash,
            bytes32(0),
            metadataURI,
            TaskStatus.Open
        );
        taskIdByKey[taskKey] = taskId;
        emit TaskCreated(taskId, guildId, domainId, taskKey);
    }

    function assignTask(uint256 taskId, address contributor) external onlyRole(TASK_ADMIN_ROLE) {
        Task storage task = _task(taskId);
        if (
            task.status != TaskStatus.Open || contributor == address(0) || block.timestamp > task.deadline
                || !domains.isActiveDomain(task.domainId)
        ) {
            revert TaskNotAssignable(taskId);
        }
        task.contributor = contributor;
        task.status = TaskStatus.Assigned;
        emit TaskAssigned(taskId, contributor);
    }

    function submitEvidence(uint256 taskId, bytes32 evidenceHash) external {
        Task storage task = _task(taskId);
        if (
            task.status != TaskStatus.Assigned || task.contributor != msg.sender || evidenceHash == bytes32(0)
                || block.timestamp > task.deadline || !domains.isActiveDomain(task.domainId)
        ) {
            revert UnauthorizedContributor();
        }
        task.submittedEvidenceHash = evidenceHash;
        task.status = TaskStatus.Submitted;
        emit TaskEvidenceSubmitted(taskId, msg.sender, evidenceHash);
    }

    function cancelTask(uint256 taskId, bytes32 reasonHash) external onlyRole(TASK_ADMIN_ROLE) {
        Task storage task = _task(taskId);
        if (task.status == TaskStatus.Accepted || task.status == TaskStatus.Paid) revert InvalidStatus(taskId);
        task.status = TaskStatus.Cancelled;
        emit TaskStatusUpdated(taskId, TaskStatus.Cancelled, reasonHash);
    }

    function markAccepted(uint256 taskId, bytes32 reviewId) external {
        if (msg.sender != evidenceReview) revert OnlyEvidenceReview();
        Task storage task = _task(taskId);
        if (task.status != TaskStatus.Submitted && task.status != TaskStatus.Disputed) revert InvalidStatus(taskId);
        task.status = TaskStatus.Accepted;
        emit TaskStatusUpdated(taskId, TaskStatus.Accepted, reviewId);
    }

    function markRejected(uint256 taskId, bytes32 reviewId) external {
        if (msg.sender != evidenceReview) revert OnlyEvidenceReview();
        Task storage task = _task(taskId);
        if (task.status != TaskStatus.Submitted && task.status != TaskStatus.Disputed) revert InvalidStatus(taskId);
        task.status = TaskStatus.Rejected;
        emit TaskStatusUpdated(taskId, TaskStatus.Rejected, reviewId);
    }

    function markDisputed(uint256 taskId, bytes32 reviewId) external {
        if (msg.sender != evidenceReview) revert OnlyEvidenceReview();
        Task storage task = _task(taskId);
        if (task.status != TaskStatus.Submitted && task.status != TaskStatus.Accepted) revert InvalidStatus(taskId);
        task.status = TaskStatus.Disputed;
        emit TaskStatusUpdated(taskId, TaskStatus.Disputed, reviewId);
    }

    function markReviewRevoked(uint256 taskId, bytes32 reviewId) external {
        if (msg.sender != evidenceReview) revert OnlyEvidenceReview();
        Task storage task = _task(taskId);
        if (task.status == TaskStatus.Paid || task.status == TaskStatus.Cancelled) revert InvalidStatus(taskId);
        task.status = TaskStatus.Rejected;
        emit TaskStatusUpdated(taskId, TaskStatus.Rejected, reviewId);
    }

    function markPaid(uint256 taskId, bytes32 paymentReference) external onlyRole(TASK_ADMIN_ROLE) {
        Task storage task = _task(taskId);
        if (task.status != TaskStatus.Accepted) revert InvalidStatus(taskId);
        task.status = TaskStatus.Paid;
        emit TaskStatusUpdated(taskId, TaskStatus.Paid, paymentReference);
    }

    function getTask(uint256 taskId) external view returns (Task memory) {
        return _task(taskId);
    }

    function _task(uint256 taskId) internal view returns (Task storage task) {
        task = _tasks[taskId];
        if (task.taskId == 0) revert UnknownTask(taskId);
    }
}
