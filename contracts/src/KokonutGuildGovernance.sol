// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Address} from "@openzeppelin/contracts/utils/Address.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {KokonutGuildDomain} from "./KokonutGuildDomain.sol";
import {KokonutTaskBoard} from "./KokonutTaskBoard.sol";

/// @title Kokonut Guild Governance
/// @notice Lazy-consensus motions for allowlisted operational Guild actions.
/// @dev This contract cannot move ETH or execute unallowlisted treasury calls.
contract KokonutGuildGovernance is AccessControl, ReentrancyGuard {
    using Address for address;

    uint256 public constant MAX_CALLDATA_BYTES = 256;
    uint256 public constant MAX_RETURN_DATA_BYTES = 4096;
    uint256 public constant MIN_OBJECTION_WINDOW = 1 days;

    bytes32 public constant PROPOSER_ROLE = keccak256("PROPOSER_ROLE");
    bytes32 public constant OBJECTOR_ROLE = keccak256("OBJECTOR_ROLE");
    bytes32 public constant EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");

    enum MotionStatus {
        Open,
        Passed,
        Rejected,
        Executed,
        Cancelled
    }

    struct Motion {
        uint256 motionId;
        bytes32 guildId;
        address proposer;
        address target;
        bytes32 dataHash;
        bytes data;
        uint64 objectionDeadline;
        uint32 objectionCount;
        bytes32 objectionReasonHash;
        MotionStatus status;
    }

    uint256 public nextMotionId = 1;
    mapping(uint256 motionId => Motion motion) private _motions;
    mapping(address target => bool allowed) public allowedTargets;
    mapping(address target => mapping(bytes4 selector => bool allowed)) public allowedSelectors;
    mapping(address target => bool guildScopedTarget) public guildScopedTargets;

    error InvalidMotion();
    error TargetNotAllowed(address target);
    error MotionNotOpen(uint256 motionId);
    error ObjectionWindowOpen(uint256 motionId);
    error ObjectionWindowClosed(uint256 motionId);
    error MotionNotPassed(uint256 motionId);
    error ValueNotAllowed();

    event TargetPermissionUpdated(address indexed target, bool allowed);
    event TargetSelectorPermissionUpdated(address indexed target, bytes4 indexed selector, bool allowed);
    event GuildScopedTargetUpdated(address indexed target, bool guildScoped);
    event MotionCreated(
        uint256 indexed motionId,
        bytes32 indexed guildId,
        address indexed proposer,
        address target,
        bytes32 dataHash,
        uint64 objectionDeadline
    );
    event MotionObjected(uint256 indexed motionId, address indexed objector, bytes32 reasonHash);
    event MotionFinalized(uint256 indexed motionId, MotionStatus status);
    event MotionExecuted(uint256 indexed motionId, bytes returnData);

    constructor(address admin) {
        if (admin == address(0)) revert InvalidMotion();
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(PROPOSER_ROLE, admin);
        _grantRole(OBJECTOR_ROLE, admin);
        _grantRole(EXECUTOR_ROLE, admin);
    }

    function setTargetAllowed(address target, bool allowed) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (target == address(0)) revert InvalidMotion();
        allowedTargets[target] = allowed;
        emit TargetPermissionUpdated(target, allowed);
    }

    function setTargetSelectorAllowed(address target, bytes4 selector, bool allowed)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (target == address(0) || !allowedTargets[target]) revert InvalidMotion();
        allowedSelectors[target][selector] = allowed;
        emit TargetSelectorPermissionUpdated(target, selector, allowed);
    }

    function setGuildScopedTarget(address target, bool scoped) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (target == address(0) || !allowedTargets[target]) revert InvalidMotion();
        guildScopedTargets[target] = scoped;
        emit GuildScopedTargetUpdated(target, scoped);
    }

    function createMotion(bytes32 guildId, address target, bytes calldata data, uint64 objectionDeadline)
        external
        onlyRole(PROPOSER_ROLE)
        returns (uint256 motionId)
    {
        if (
            guildId == bytes32(0) || !allowedTargets[target] || data.length > MAX_CALLDATA_BYTES
                || objectionDeadline <= block.timestamp || (objectionDeadline - block.timestamp) < MIN_OBJECTION_WINDOW
                || data.length < 4 || !allowedSelectors[target][_selector(data)]
                || (guildScopedTargets[target] && !_matchesGuild(target, data, guildId))
        ) {
            revert InvalidMotion();
        }
        motionId = nextMotionId++;
        _motions[motionId] = Motion(
            motionId,
            guildId,
            msg.sender,
            target,
            keccak256(data),
            data,
            objectionDeadline,
            0,
            bytes32(0),
            MotionStatus.Open
        );
        emit MotionCreated(motionId, guildId, msg.sender, target, keccak256(data), objectionDeadline);
    }

    function objectMotion(uint256 motionId, bytes32 reasonHash) external onlyRole(OBJECTOR_ROLE) {
        Motion storage motion = _motion(motionId);
        if (motion.status != MotionStatus.Open) revert MotionNotOpen(motionId);
        if (block.timestamp > motion.objectionDeadline) revert ObjectionWindowClosed(motionId);
        motion.objectionCount++;
        motion.objectionReasonHash = reasonHash;
        emit MotionObjected(motionId, msg.sender, reasonHash);
    }

    function finalizeMotion(uint256 motionId) external {
        Motion storage motion = _motion(motionId);
        if (motion.status != MotionStatus.Open) revert MotionNotOpen(motionId);
        if (block.timestamp <= motion.objectionDeadline) revert ObjectionWindowOpen(motionId);
        motion.status = motion.objectionCount == 0 ? MotionStatus.Passed : MotionStatus.Rejected;
        emit MotionFinalized(motionId, motion.status);
    }

    function cancelMotion(uint256 motionId) external onlyRole(DEFAULT_ADMIN_ROLE) {
        Motion storage motion = _motion(motionId);
        if (motion.status != MotionStatus.Open && motion.status != MotionStatus.Passed) revert MotionNotOpen(motionId);
        motion.status = MotionStatus.Cancelled;
        emit MotionFinalized(motionId, MotionStatus.Cancelled);
    }

    function executeMotion(uint256 motionId) external onlyRole(EXECUTOR_ROLE) nonReentrant {
        Motion storage motion = _motion(motionId);
        if (motion.status != MotionStatus.Passed) revert MotionNotPassed(motionId);
        if (!allowedTargets[motion.target] || !allowedSelectors[motion.target][_selectorMemory(motion.data)]) {
            revert TargetNotAllowed(motion.target);
        }
        if (guildScopedTargets[motion.target] && !_matchesGuild(motion.target, motion.data, motion.guildId)) {
            revert InvalidMotion();
        }
        motion.status = MotionStatus.Executed;
        bytes memory returnData = motion.target.functionCall(motion.data);
        if (returnData.length > MAX_RETURN_DATA_BYTES) revert InvalidMotion();
        emit MotionExecuted(motionId, returnData);
    }

    function getMotion(uint256 motionId) external view returns (Motion memory) {
        return _motion(motionId);
    }

    function _motion(uint256 motionId) internal view returns (Motion storage motion) {
        motion = _motions[motionId];
        if (motion.motionId == 0) revert InvalidMotion();
    }

    function _selector(bytes calldata data) internal pure returns (bytes4 selector) {
        assembly {
            selector := calldataload(data.offset)
        }
    }

    function _selectorMemory(bytes memory data) internal pure returns (bytes4 selector) {
        assembly {
            selector := mload(add(data, 32))
        }
    }

    function _matchesGuild(address target, bytes memory data, bytes32 guildId) internal view returns (bool) {
        bytes4 selector = _selectorMemory(data);
        bytes memory arguments = _arguments(data);
        if (target == address(0)) return false;
        if (selector == KokonutTaskBoard.cancelTask.selector || selector == KokonutTaskBoard.markPaid.selector) {
            (uint256 taskId,) = abi.decode(arguments, (uint256, bytes32));
            return KokonutTaskBoard(target).getTask(taskId).guildId == guildId;
        }
        if (selector == KokonutGuildDomain.setStatus.selector) {
            (uint256 domainId,) = abi.decode(arguments, (uint256, KokonutGuildDomain.DomainStatus));
            return KokonutGuildDomain(target).getDomain(domainId).guildId == guildId;
        }
        return false;
    }

    function _arguments(bytes memory data) internal pure returns (bytes memory arguments) {
        arguments = new bytes(data.length - 4);
        for (uint256 i; i < arguments.length; ++i) {
            arguments[i] = data[i + 4];
        }
    }
}
