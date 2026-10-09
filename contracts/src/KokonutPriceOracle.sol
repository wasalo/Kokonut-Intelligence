// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

/// @title Kokonut Price Oracle
/// @notice On-chain price feed with EAS attestation linkage.
/// @dev Prices are updated by authorized updaters and linked to EAS attestations.
contract KokonutPriceOracle is Initializable, AccessControlUpgradeable, PausableUpgradeable, UUPSUpgradeable {
    bytes32 public constant UPDATER_ROLE = keccak256("UPDATER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    error ZeroAddress();
    error ZeroPrice();
    error StaleTimestamp(bytes32 feedKey, uint256 lastUpdate, uint256 blockTime);
    error BelowConfidenceThreshold(bytes32 feedKey, uint256 confidence, uint256 required);

    struct PriceFeed {
        uint256 price;
        uint256 timestamp;
        string source;
        bytes32 attestationUid;
        uint256 confidence;
        uint256 updateCount;
    }

    struct PriceHistoryEntry {
        uint256 price;
        uint256 timestamp;
        bytes32 attestationUid;
        uint256 confidence;
    }

    mapping(bytes32 feedKey => PriceFeed) public feeds;
    mapping(bytes32 feedKey => PriceHistoryEntry[]) public history;
    mapping(bytes32 feedKey => uint256) public confidenceThresholds;
    mapping(bytes32 feedKey => uint256) public maxAge;

    uint256 public constant MAX_HISTORY = 100;

    event PriceUpdated(
        bytes32 indexed feedKey,
        uint256 price,
        uint256 timestamp,
        string source,
        bytes32 attestationUid,
        uint256 confidence,
        uint256 updateCount
    );
    event ConfidenceThresholdSet(bytes32 indexed feedKey, uint256 threshold);
    event MaxAgeSet(bytes32 indexed feedKey, uint256 maxAgeSeconds);

    constructor() {
        _disableInitializers();
    }

    function initialize(address admin, address updater, address pauser, address upgrader) external initializer {
        if (admin == address(0) || updater == address(0) || pauser == address(0) || upgrader == address(0)) {
            revert ZeroAddress();
        }

        __AccessControl_init();
        __Pausable_init();

        _setRoleAdmin(UPGRADER_ROLE, UPGRADER_ROLE);
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(UPDATER_ROLE, updater);
        _grantRole(PAUSER_ROLE, pauser);
        _grantRole(UPGRADER_ROLE, upgrader);
    }

    function updatePrice(
        bytes32 feedKey,
        uint256 price,
        string calldata source,
        bytes32 attestationUid,
        uint256 confidence
    ) external onlyRole(UPDATER_ROLE) whenNotPaused {
        if (price == 0) revert ZeroPrice();

        uint256 requiredConfidence = confidenceThresholds[feedKey];
        if (requiredConfidence > 0 && confidence < requiredConfidence) {
            revert BelowConfidenceThreshold(feedKey, confidence, requiredConfidence);
        }

        PriceFeed storage feed = feeds[feedKey];
        if (feed.timestamp > 0) {
            uint256 age = block.timestamp - feed.timestamp;
            uint256 maxFeedAge = maxAge[feedKey];
            if (maxFeedAge > 0 && age > maxFeedAge) {
                revert StaleTimestamp(feedKey, feed.timestamp, block.timestamp);
            }
        }

        feed.price = price;
        feed.timestamp = block.timestamp;
        feed.source = source;
        feed.attestationUid = attestationUid;
        feed.confidence = confidence;
        feed.updateCount++;

        PriceHistoryEntry[] storage entries = history[feedKey];
        if (entries.length >= MAX_HISTORY) {
            for (uint256 i = 0; i < entries.length - 1; i++) {
                entries[i] = entries[i + 1];
            }
            entries.pop();
        }
        entries.push(
            PriceHistoryEntry({
                price: price, timestamp: block.timestamp, attestationUid: attestationUid, confidence: confidence
            })
        );

        emit PriceUpdated(feedKey, price, block.timestamp, source, attestationUid, confidence, feed.updateCount);
    }

    function getPrice(bytes32 feedKey) external view returns (PriceFeed memory) {
        return feeds[feedKey];
    }

    function getPriceHistory(bytes32 feedKey, uint256 count) external view returns (PriceHistoryEntry[] memory) {
        PriceHistoryEntry[] storage entries = history[feedKey];
        uint256 len = count > entries.length ? entries.length : count;
        PriceHistoryEntry[] memory result = new PriceHistoryEntry[](len);
        uint256 start = entries.length - len;
        for (uint256 i = 0; i < len; i++) {
            result[i] = entries[start + i];
        }
        return result;
    }

    function setConfidenceThreshold(bytes32 feedKey, uint256 threshold) external onlyRole(UPDATER_ROLE) {
        confidenceThresholds[feedKey] = threshold;
        emit ConfidenceThresholdSet(feedKey, threshold);
    }

    function setMaxAge(bytes32 feedKey, uint256 maxAgeSeconds) external onlyRole(UPDATER_ROLE) {
        maxAge[feedKey] = maxAgeSeconds;
        emit MaxAgeSet(feedKey, maxAgeSeconds);
    }

    function feedExists(bytes32 feedKey) external view returns (bool) {
        return feeds[feedKey].timestamp > 0;
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    function supportsInterface(bytes4 interfaceId) public view override(AccessControlUpgradeable) returns (bool) {
        return super.supportsInterface(interfaceId);
    }

    function _authorizeUpgrade(address) internal override onlyRole(UPGRADER_ROLE) {}
}
