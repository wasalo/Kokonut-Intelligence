// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/// @title Kokonut Guild Registry
/// @notice Registers Guild identities and their steward authority.
contract KokonutGuildRegistry is AccessControl, Pausable {
    bytes32 public constant GUILD_ADMIN_ROLE = keccak256("GUILD_ADMIN_ROLE");

    enum GuildStatus {
        Active,
        Paused,
        Deprecated
    }

    struct Guild {
        bytes32 guildId;
        bytes32 guildKey;
        string name;
        string metadataURI;
        address steward;
        GuildStatus status;
    }

    mapping(bytes32 guildId => Guild guild) private _guilds;
    mapping(bytes32 guildKey => bytes32 guildId) public guildIdByKey;

    error InvalidGuildId();
    error GuildAlreadyExists(bytes32 guildId);
    error GuildKeyAlreadyExists(bytes32 guildKey);
    error UnknownGuild(bytes32 guildId);
    error InvalidSteward();

    event GuildCreated(bytes32 indexed guildId, bytes32 indexed guildKey, string name, address indexed steward);
    event GuildMetadataUpdated(bytes32 indexed guildId, string metadataURI);
    event GuildStewardUpdated(bytes32 indexed guildId, address indexed steward);
    event GuildStatusUpdated(bytes32 indexed guildId, GuildStatus status);

    constructor(address admin) {
        if (admin == address(0)) revert InvalidSteward();
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(GUILD_ADMIN_ROLE, admin);
    }

    function createGuild(
        bytes32 guildId,
        bytes32 guildKey,
        string calldata name,
        string calldata metadataURI,
        address steward
    ) external onlyRole(GUILD_ADMIN_ROLE) whenNotPaused {
        if (guildId == bytes32(0) || guildKey == bytes32(0)) revert InvalidGuildId();
        if (_guilds[guildId].guildId != bytes32(0)) revert GuildAlreadyExists(guildId);
        if (guildIdByKey[guildKey] != bytes32(0)) revert GuildKeyAlreadyExists(guildKey);
        if (steward == address(0)) revert InvalidSteward();

        _guilds[guildId] = Guild(guildId, guildKey, name, metadataURI, steward, GuildStatus.Active);
        guildIdByKey[guildKey] = guildId;
        emit GuildCreated(guildId, guildKey, name, steward);
    }

    function setMetadata(bytes32 guildId, string calldata metadataURI) external onlyRole(GUILD_ADMIN_ROLE) {
        _guild(guildId).metadataURI = metadataURI;
        emit GuildMetadataUpdated(guildId, metadataURI);
    }

    function setSteward(bytes32 guildId, address steward) external onlyRole(GUILD_ADMIN_ROLE) {
        if (steward == address(0)) revert InvalidSteward();
        _guild(guildId).steward = steward;
        emit GuildStewardUpdated(guildId, steward);
    }

    function setStatus(bytes32 guildId, GuildStatus status) external onlyRole(GUILD_ADMIN_ROLE) {
        _guild(guildId).status = status;
        emit GuildStatusUpdated(guildId, status);
    }

    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    function getGuild(bytes32 guildId) external view returns (Guild memory) {
        return _guild(guildId);
    }

    function guildExists(bytes32 guildId) external view returns (bool) {
        return _guilds[guildId].guildId != bytes32(0);
    }

    function isActiveGuild(bytes32 guildId) external view returns (bool) {
        return _guilds[guildId].status == GuildStatus.Active;
    }

    function isGuildSteward(bytes32 guildId, address account) external view returns (bool) {
        return _guilds[guildId].steward == account && _guilds[guildId].status == GuildStatus.Active;
    }

    function _guild(bytes32 guildId) internal view returns (Guild storage guild) {
        guild = _guilds[guildId];
        if (guild.guildId == bytes32(0)) revert UnknownGuild(guildId);
    }
}
