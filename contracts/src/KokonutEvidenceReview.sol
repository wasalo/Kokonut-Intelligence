// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {KokonutTaskBoard} from "./KokonutTaskBoard.sol";

/// @title Kokonut Evidence Review
/// @notice Records review decisions and dispute outcomes for submitted tasks.
contract KokonutEvidenceReview is AccessControl {
    bytes32 public constant REVIEWER_ROLE = keccak256("REVIEWER_ROLE");

    enum ReviewDecision {
        Accepted,
        Rejected
    }

    enum ReviewStatus {
        Accepted,
        Rejected,
        Disputed,
        Revoked
    }

    struct Review {
        bytes32 reviewId;
        uint256 taskId;
        address reviewer;
        bytes32 evidenceHash;
        bytes32 notesHash;
        bytes32 disputeReasonHash;
        bytes32 resolutionHash;
        ReviewDecision decision;
        ReviewStatus status;
    }

    KokonutTaskBoard public immutable tasks;
    mapping(bytes32 reviewId => Review review) private _reviews;
    mapping(uint256 taskId => bytes32 reviewId) public reviewIdByTask;

    error InvalidReview();
    error ReviewExists(bytes32 reviewId);
    error UnknownReview(bytes32 reviewId);
    error ReviewNotDisputable(bytes32 reviewId);
    error UnauthorizedDisputer();

    event EvidenceReviewed(
        bytes32 indexed reviewId,
        uint256 indexed taskId,
        address indexed reviewer,
        ReviewDecision decision,
        bytes32 evidenceHash,
        bytes32 notesHash
    );
    event EvidenceDisputed(bytes32 indexed reviewId, address indexed disputer, bytes32 reasonHash);
    event EvidenceDisputeResolved(bytes32 indexed reviewId, bool accepted, bytes32 resolutionHash);
    event EvidenceRevoked(bytes32 indexed reviewId, bytes32 reasonHash);

    constructor(address admin, KokonutTaskBoard taskBoard) {
        if (admin == address(0) || address(taskBoard) == address(0)) revert InvalidReview();
        tasks = taskBoard;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(REVIEWER_ROLE, admin);
    }

    function reviewEvidence(
        bytes32 reviewId,
        uint256 taskId,
        ReviewDecision decision,
        bytes32 evidenceHash,
        bytes32 notesHash
    ) external onlyRole(REVIEWER_ROLE) {
        if (reviewId == bytes32(0) || evidenceHash == bytes32(0)) revert InvalidReview();
        if (_reviews[reviewId].reviewId != bytes32(0)) revert ReviewExists(reviewId);
        if (reviewIdByTask[taskId] != bytes32(0)) revert InvalidReview();

        KokonutTaskBoard.Task memory task = tasks.getTask(taskId);
        if (task.status != KokonutTaskBoard.TaskStatus.Submitted) revert InvalidReview();
        if (task.submittedEvidenceHash != evidenceHash) revert InvalidReview();

        _reviews[reviewId] = Review(
            reviewId,
            taskId,
            msg.sender,
            evidenceHash,
            notesHash,
            bytes32(0),
            bytes32(0),
            decision,
            decision == ReviewDecision.Accepted ? ReviewStatus.Accepted : ReviewStatus.Rejected
        );
        reviewIdByTask[taskId] = reviewId;
        if (decision == ReviewDecision.Accepted) tasks.markAccepted(taskId, reviewId);
        else tasks.markRejected(taskId, reviewId);
        emit EvidenceReviewed(reviewId, taskId, msg.sender, decision, evidenceHash, notesHash);
    }

    function disputeReview(bytes32 reviewId, bytes32 reasonHash) external {
        Review storage review = _review(reviewId);
        KokonutTaskBoard.Task memory task = tasks.getTask(review.taskId);
        if (msg.sender != task.contributor && !hasRole(REVIEWER_ROLE, msg.sender)) revert UnauthorizedDisputer();
        if (review.status != ReviewStatus.Accepted && review.status != ReviewStatus.Rejected) {
            revert ReviewNotDisputable(reviewId);
        }
        review.status = ReviewStatus.Disputed;
        review.disputeReasonHash = reasonHash;
        tasks.markDisputed(review.taskId, reviewId);
        emit EvidenceDisputed(reviewId, msg.sender, reasonHash);
    }

    function resolveDispute(bytes32 reviewId, bool accepted, bytes32 resolutionHash) external onlyRole(REVIEWER_ROLE) {
        Review storage review = _review(reviewId);
        if (review.status != ReviewStatus.Disputed) revert ReviewNotDisputable(reviewId);
        review.resolutionHash = resolutionHash;
        review.status = accepted ? ReviewStatus.Accepted : ReviewStatus.Rejected;
        if (accepted) tasks.markAccepted(review.taskId, reviewId);
        else tasks.markRejected(review.taskId, reviewId);
        emit EvidenceDisputeResolved(reviewId, accepted, resolutionHash);
    }

    function revokeReview(bytes32 reviewId, bytes32 reasonHash) external onlyRole(DEFAULT_ADMIN_ROLE) {
        Review storage review = _review(reviewId);
        if (review.status == ReviewStatus.Revoked) revert ReviewNotDisputable(reviewId);
        review.status = ReviewStatus.Revoked;
        emit EvidenceRevoked(reviewId, reasonHash);
    }

    function getReview(bytes32 reviewId) external view returns (Review memory) {
        return _review(reviewId);
    }

    function _review(bytes32 reviewId) internal view returns (Review storage review) {
        review = _reviews[reviewId];
        if (review.reviewId == bytes32(0)) revert UnknownReview(reviewId);
    }
}
