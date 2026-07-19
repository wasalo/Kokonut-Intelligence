// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Address} from "@openzeppelin/contracts/utils/Address.sol";

/// @title Kokonut Guild Upgrade Timelock
/// @notice Delays KGP implementation upgrades behind separate proposer/executor roles.
contract KokonutGuildUpgradeTimelock is AccessControl {
    // Timelock readiness is a wall-clock policy window; small validator drift is acceptable.
    using Address for address;

    bytes32 public constant ERC1967_IMPLEMENTATION_SLOT =
        0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    bytes32 public constant PROPOSER_ROLE = keccak256("PROPOSER_ROLE");
    bytes32 public constant EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");

    uint256 public immutable minDelay;
    address public immutable approvedProxy;

    struct Upgrade {
        address proxy;
        address implementation;
        address expectedCurrentImplementation;
        bytes data;
        uint256 eta;
        bool executed;
        bool cancelled;
    }

    mapping(bytes32 upgradeId => Upgrade upgrade) private _upgrades;

    error InvalidUpgrade();
    error UpgradeNotReady(bytes32 upgradeId, uint256 eta);
    error UpgradeUnavailable(bytes32 upgradeId);
    error Unauthorized();
    error UpgradeCompatibilityFailed();

    event UpgradeQueued(bytes32 indexed upgradeId, address indexed proxy, address indexed implementation, uint256 eta);
    event UpgradeCancelled(bytes32 indexed upgradeId);
    event UpgradeExecuted(bytes32 indexed upgradeId);

    constructor(address admin, address proposer, address executor, uint256 delay, address proxy) {
        if (
            admin == address(0) || proposer == address(0) || executor == address(0) || delay == 0 || admin == proposer
                || admin == executor || proposer == executor || proxy.code.length == 0
        ) {
            revert InvalidUpgrade();
        }
        minDelay = delay;
        approvedProxy = proxy;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(PROPOSER_ROLE, proposer);
        _grantRole(EXECUTOR_ROLE, executor);
    }

    function queueUpgrade(address proxy, address implementation, bytes calldata data)
        external
        onlyRole(PROPOSER_ROLE)
        returns (bytes32 upgradeId)
    {
        if (proxy != approvedProxy || implementation.code.length == 0) revert InvalidUpgrade();
        _assertUUPSImplementation(implementation);
        address currentImplementation = _proxyImplementation(proxy);
        if (currentImplementation == address(0)) revert UpgradeCompatibilityFailed();
        upgradeId = keccak256(abi.encode(proxy, implementation, data, block.timestamp));
        if (_upgrades[upgradeId].eta != 0) revert InvalidUpgrade();
        uint256 eta = block.timestamp + minDelay;
        _upgrades[upgradeId] = Upgrade(proxy, implementation, currentImplementation, data, eta, false, false);
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
        // forge-lint: disable-next-line(block-timestamp)
        if (block.timestamp < upgrade.eta) revert UpgradeNotReady(upgradeId, upgrade.eta);
        _assertUUPSImplementation(upgrade.implementation);
        if (_proxyImplementation(upgrade.proxy) != upgrade.expectedCurrentImplementation) {
            revert UpgradeCompatibilityFailed();
        }
        upgrade.executed = true;
        // Address.functionCall reverts on failure; the return bytes are not needed.
        // slither-disable-next-line unused-return
        upgrade.proxy
            .functionCall(
                abi.encodeWithSignature("upgradeToAndCall(address,bytes)", upgrade.implementation, upgrade.data)
            );
        emit UpgradeExecuted(upgradeId);
    }

    function getUpgrade(bytes32 upgradeId) external view returns (Upgrade memory) {
        if (!hasRole(PROPOSER_ROLE, msg.sender) && !hasRole(EXECUTOR_ROLE, msg.sender)) revert Unauthorized();
        return _upgrade(upgradeId);
    }

    function _upgrade(bytes32 upgradeId) internal view returns (Upgrade storage upgrade) {
        upgrade = _upgrades[upgradeId];
        if (upgrade.eta == 0) revert UpgradeUnavailable(upgradeId);
    }

    function _assertUUPSImplementation(address implementation) internal view {
        (bool ok, bytes memory result) = implementation.staticcall(abi.encodeWithSignature("proxiableUUID()"));
        if (!ok || result.length != 32 || abi.decode(result, (bytes32)) != ERC1967_IMPLEMENTATION_SLOT) {
            revert UpgradeCompatibilityFailed();
        }
    }

    function _proxyImplementation(address proxy) internal view returns (address implementation) {
        (bool ok, bytes memory result) = proxy.staticcall(abi.encodeWithSignature("implementation()"));
        if (!ok || result.length != 32) return address(0);
        implementation = abi.decode(result, (address));
    }
}
