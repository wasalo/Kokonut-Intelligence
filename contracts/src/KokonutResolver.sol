// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {SchemaResolver} from "@eas-contracts/resolver/SchemaResolver.sol";
import {IEAS, Attestation} from "@eas-contracts/IEAS.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title KokonutResolver
/// @notice EAS resolver that gates attestation/revocation to allowed attesters.
/// @dev Deploy one resolver per EAS deployment. To "upgrade", deploy a new resolver
///      and register new schemas pointing to it. Old schemas keep the old resolver.
contract KokonutResolver is SchemaResolver, Ownable {
    event AttesterAdded(address indexed attester);
    event AttesterRemoved(address indexed attester);

    mapping(address => bool) public allowedAttesters;

    /// @param eas Address of the EAS contract on this chain.
    /// @param owner Address that can manage allowed attesters.
    /// @param initialAttesters Addresses to allow immediately.
    constructor(IEAS eas, address owner, address[] memory initialAttesters) SchemaResolver(eas) Ownable(owner) {
        for (uint256 i = 0; i < initialAttesters.length; i++) {
            allowedAttesters[initialAttesters[i]] = true;
            emit AttesterAdded(initialAttesters[i]);
        }
    }

    function addAttester(address attester) external onlyOwner {
        require(attester != address(0), "Zero address");
        allowedAttesters[attester] = true;
        emit AttesterAdded(attester);
    }

    function removeAttester(address attester) external onlyOwner {
        require(attester != address(0), "Zero address");
        allowedAttesters[attester] = false;
        emit AttesterRemoved(attester);
    }

    function isPayable() public pure override returns (bool) {
        return false;
    }

    function onAttest(Attestation calldata attestation, uint256) internal override returns (bool) {
        return allowedAttesters[attestation.attester];
    }

    function onRevoke(Attestation calldata attestation, uint256) internal override returns (bool) {
        return allowedAttesters[attestation.attester];
    }
}
