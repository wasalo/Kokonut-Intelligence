// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {KokonutGuildRegistry} from "./KokonutGuildRegistry.sol";

/// @title Kokonut Guild Domains
/// @notice Registers Guild-scoped teams/domains used by tasks and reputation.
contract KokonutGuildDomain is AccessControl {
    bytes32 public constant DOMAIN_ADMIN_ROLE = keccak256("DOMAIN_ADMIN_ROLE");
    uint256 public constant DEPRECATION_GRACE_PERIOD = 48 hours;

    enum DomainStatus {
        Active,
        Paused,
        Deprecated
    }

    struct Domain {
        uint256 domainId;
        bytes32 guildId;
        uint256 parentDomainId;
        string name;
        string metadataURI;
        DomainStatus status;
        uint256 deprecationTime;
    }

    KokonutGuildRegistry public immutable registry;
    uint256 public nextDomainId = 1;
    mapping(uint256 domainId => Domain domain) private _domains;

    error InvalidRegistry();
    error InvalidDomain();
    error UnknownDomain(uint256 domainId);
    error ParentDomainMismatch();

    event DomainCreated(
        uint256 indexed domainId, bytes32 indexed guildId, uint256 indexed parentDomainId, string name, address creator
    );
    event DomainMetadataUpdated(uint256 indexed domainId, string metadataURI);
    event DomainStatusUpdated(uint256 indexed domainId, DomainStatus status);

    constructor(address admin, KokonutGuildRegistry guildRegistry) {
        if (admin == address(0) || address(guildRegistry) == address(0)) revert InvalidRegistry();
        registry = guildRegistry;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(DOMAIN_ADMIN_ROLE, admin);
    }

    function createDomain(bytes32 guildId, uint256 parentDomainId, string calldata name, string calldata metadataURI)
        external
        onlyRole(DOMAIN_ADMIN_ROLE)
        returns (uint256 domainId)
    {
        if (!registry.isActiveGuild(guildId)) revert InvalidDomain();
        if (parentDomainId != 0) {
            Domain storage parent = _domain(parentDomainId);
            if (parent.guildId != guildId || parent.status != DomainStatus.Active) revert ParentDomainMismatch();
        }

        domainId = nextDomainId++;
        _domains[domainId] = Domain(domainId, guildId, parentDomainId, name, metadataURI, DomainStatus.Active, 0);
        emit DomainCreated(domainId, guildId, parentDomainId, name, msg.sender);
    }

    function setMetadata(uint256 domainId, string calldata metadataURI) external onlyRole(DOMAIN_ADMIN_ROLE) {
        _domain(domainId).metadataURI = metadataURI;
        emit DomainMetadataUpdated(domainId, metadataURI);
    }

    function setStatus(uint256 domainId, DomainStatus status) external onlyRole(DOMAIN_ADMIN_ROLE) {
        Domain storage domain = _domain(domainId);
        if (status == DomainStatus.Deprecated) {
            domain.deprecationTime = block.timestamp;
        }
        domain.status = status;
        emit DomainStatusUpdated(domainId, status);
    }

    function getDomain(uint256 domainId) external view returns (Domain memory) {
        return _domain(domainId);
    }

    function isActiveDomain(uint256 domainId) external view returns (bool) {
        Domain storage domain = _domains[domainId];
        if (!registry.isActiveGuild(domain.guildId)) return false;
        if (domain.status == DomainStatus.Active) return true;
        if (
            domain.status == DomainStatus.Deprecated && domain.deprecationTime > 0
                && block.timestamp < domain.deprecationTime + DEPRECATION_GRACE_PERIOD
        ) {
            return true;
        }
        return false;
    }

    function guildIdOf(uint256 domainId) external view returns (bytes32) {
        return _domain(domainId).guildId;
    }

    function isDomainSteward(uint256 domainId, address account) external view returns (bool) {
        Domain storage domain = _domains[domainId];
        return domain.status == DomainStatus.Active && registry.isActiveGuild(domain.guildId)
            && registry.isGuildSteward(domain.guildId, account);
    }

    function _domain(uint256 domainId) internal view returns (Domain storage domain) {
        domain = _domains[domainId];
        if (domain.domainId == 0) revert UnknownDomain(domainId);
    }
}
