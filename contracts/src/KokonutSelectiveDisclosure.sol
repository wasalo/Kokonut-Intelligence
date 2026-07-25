// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

/// @title Kokonut Selective Disclosure
/// @notice On-chain Merkle root verifier for selective field disclosure.
/// @dev Stores disclosure roots per attestation and verifies inclusion proofs.
contract KokonutSelectiveDisclosure is Initializable, AccessControlUpgradeable, PausableUpgradeable, UUPSUpgradeable {
    bytes32 public constant ATTESTER_ROLE = keccak256("ATTESTER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    error ZeroAddress();
    error ZeroHash();
    error RootAlreadySet(bytes32 attestationUid);
    error ProofVerificationFailed();

    mapping(bytes32 attestationUid => bytes32 root) public disclosureRoots;
    mapping(bytes32 attestationUid => bool) public isSet;

    event RootSet(bytes32 indexed attestationUid, bytes32 root, uint256 timestamp);
    event ProofVerified(bytes32 indexed attestationUid, bytes32 leaf, bool valid);

    constructor() {
        _disableInitializers();
    }

    function initialize(address admin, address attester, address pauser, address upgrader) external initializer {
        if (admin == address(0) || attester == address(0) || pauser == address(0) || upgrader == address(0)) {
            revert ZeroAddress();
        }

        __AccessControl_init();
        __Pausable_init();

        _setRoleAdmin(UPGRADER_ROLE, UPGRADER_ROLE);
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ATTESTER_ROLE, attester);
        _grantRole(PAUSER_ROLE, pauser);
        _grantRole(UPGRADER_ROLE, upgrader);
    }

    function setRoot(bytes32 attestationUid, bytes32 root) external onlyRole(ATTESTER_ROLE) whenNotPaused {
        if (root == bytes32(0)) revert ZeroHash();
        if (isSet[attestationUid]) revert RootAlreadySet(attestationUid);

        disclosureRoots[attestationUid] = root;
        isSet[attestationUid] = true;

        emit RootSet(attestationUid, root, block.timestamp);
    }

    function verifyProof(bytes32 attestationUid, bytes32 leaf, bytes32[] calldata proof, uint8[] calldata proofFlags)
        external
        view
        returns (bool)
    {
        bytes32 root = disclosureRoots[attestationUid];
        if (root == bytes32(0)) return false;

        bytes32 computed = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            if (proofFlags[i] == 0) {
                computed = _hashPair(computed, proof[i]);
            } else {
                computed = _hashPair(proof[i], computed);
            }
        }

        return computed == root;
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

    function _hashPair(bytes32 a, bytes32 b) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(a, b));
    }
}
