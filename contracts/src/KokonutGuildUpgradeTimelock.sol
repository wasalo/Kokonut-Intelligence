// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Address} from "@openzeppelin/contracts/utils/Address.sol";

/// @title Kokonut Guild Upgrade Timelock
/// @notice Delays KGP implementation upgrades behind separate proposer/executor roles.
contract KokonutGuildUpgradeTimelock is AccessControl {
    using Address for address;

    bytes32 public constant PROPOSER_ROLE = keccak256("PROPOSER_ROLE");
    bytes32 public constant EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");

    uint256 public immutable minDelay;

    struct Upgrade {
        address proxy;
        address implementation;
        bytes data;
        uint256 eta;
        bool executed;
        bool cancelled;
    }

    mapping(bytes32 upgradeId => Upgrade upgrade) private _upgrades;

    error InvalidUpgrade();
    error UpgradeNotReady(bytes32 upgradeId, uint256 eta);
    error UpgradeUnavailable(bytes32 upgradeId);

    event UpgradeQueued(bytes32 indexed upgradeId, address indexed proxy, address indexed implementation, uint256 eta);
    event UpgradeCancelled(bytes32 indexed upgradeId);
    event UpgradeExecuted(bytes32 indexed upgradeId);

    constructor(address admin, address proposer, address executor, uint256 delay) {
        if (admin == address(0) || proposer == address(0) || executor == address(0) || delay == 0) {
            revert InvalidUpgrade();
        }
        minDelay = delay;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(PROPOSER_ROLE, proposer);
        _grantRole(EXECUTOR_ROLE, executor);
    }

    function queueUpgrade(address proxy, address implementation, bytes calldata data)
        external
        onlyRole(PROPOSER_ROLE)
        returns (bytes32 upgradeId)
    {
        if (proxy.code.length == 0 || implementation.code.length == 0) revert InvalidUpgrade();
        upgradeId = keccak256(abi.encode(proxy, implementation, data, block.timestamp));
        if (_upgrades[upgradeId].eta != 0) revert InvalidUpgrade();
        uint256 eta = block.timestamp + minDelay;
        _upgrades[upgradeId] = Upgrade(proxy, implementation, data, eta, false, false);
        emit UpgradeQueued(upgradeId, proxy, implementation, eta);
    }

    function cancelUpgrade(bytes32 upgradeId) external onlyRole(DEFAULT_ADMIN_ROLE) {
        Upgrade storage upgrade = _upgrade(upgradeId);
        if (upgrade.executed || upgrade.cancelled) revert UpgradeUnavailable(upgradeId);
        upgrade.cancelled = true;
        emit UpgradeCancelled(upgradeId);
    }

    function executeUpgrade(bytes32 upgradeId) external onlyRole(EXECUTOR_ROLE) {
        Upgrade storage upgrade = _upgrade(upgradeId);
        if (upgrade.executed || upgrade.cancelled) revert UpgradeUnavailable(upgradeId);
        if (block.timestamp < upgrade.eta) revert UpgradeNotReady(upgradeId, upgrade.eta);
        upgrade.executed = true;
        upgrade.proxy
            .functionCall(
                abi.encodeWithSignature("upgradeToAndCall(address,bytes)", upgrade.implementation, upgrade.data)
            );
        emit UpgradeExecuted(upgradeId);
    }

    function getUpgrade(bytes32 upgradeId) external view returns (Upgrade memory) {
        return _upgrade(upgradeId);
    }

    function _upgrade(bytes32 upgradeId) internal view returns (Upgrade storage upgrade) {
        upgrade = _upgrades[upgradeId];
        if (upgrade.eta == 0) revert UpgradeUnavailable(upgradeId);
    }
}
