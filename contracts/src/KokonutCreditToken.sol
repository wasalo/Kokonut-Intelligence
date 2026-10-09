// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {ERC1155Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC1155/ERC1155Upgradeable.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";

/// @title Kokonut Credit Token
/// @notice Non-transferable ERC-1155 for carbon credit issuance and retirement.
/// @dev PostgreSQL is the canonical governed ledger. This contract records an
///      auditable, idempotent projection of issued and retired credits.
contract KokonutCreditToken is
    Initializable,
    ERC1155Upgradeable,
    AccessControlUpgradeable,
    UUPSUpgradeable,
    PausableUpgradeable
{
    bytes32 public constant ISSUER_ROLE = keccak256("ISSUER_ROLE");
    bytes32 public constant BURNER_ROLE = keccak256("BURNER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    error ZeroAddress();
    error ZeroAmount();
    error CreditAlreadyIssued(bytes32 batchId, uint256 serialNumber);
    error InsufficientBalance(uint256 tokenId, uint256 requested, uint256 available);
    error NonTransferable();
    error InvalidCreditData();

    struct CreditRecord {
        bytes32 batchId;
        uint256 vintageYear;
        address locationId;
        uint256 serialNumber;
        string jurisdiction;
        string methodology;
        bytes32 evidenceHash;
    }

    mapping(uint256 tokenId => CreditRecord) private _credits;
    mapping(uint256 tokenId => uint256) public totalIssued;
    mapping(uint256 tokenId => uint256) public totalRetired;
    mapping(bytes32 batchId => bool) public batchExists;
    mapping(uint256 tokenId => bool) public isRetired;

    event CreditIssued(
        uint256 indexed tokenId,
        bytes32 indexed batchId,
        address indexed recipient,
        uint256 amount,
        uint256 vintageYear,
        bytes32 evidenceHash
    );
    event CreditRetired(uint256 indexed tokenId, address indexed account, uint256 amount, bytes32 reasonHash);

    constructor() {
        _disableInitializers();
    }

    function initialize(
        address admin,
        address issuer,
        address burner,
        address pauser,
        address upgrader,
        string calldata initialURI
    ) external initializer {
        if (
            admin == address(0) || issuer == address(0) || burner == address(0) || pauser == address(0)
                || upgrader == address(0)
        ) {
            revert ZeroAddress();
        }

        __ERC1155_init(initialURI);
        __AccessControl_init();
        __Pausable_init();

        _setRoleAdmin(UPGRADER_ROLE, UPGRADER_ROLE);
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ISSUER_ROLE, issuer);
        _grantRole(BURNER_ROLE, burner);
        _grantRole(PAUSER_ROLE, pauser);
        _grantRole(UPGRADER_ROLE, upgrader);
    }

    function issue(
        bytes32 batchId,
        address recipient,
        uint256 amount,
        uint256 vintageYear,
        string calldata jurisdiction,
        string calldata methodology,
        bytes32 evidenceHash
    ) external onlyRole(ISSUER_ROLE) whenNotPaused {
        _issue(batchId, recipient, amount, vintageYear, jurisdiction, methodology, evidenceHash);
    }

    function _issue(
        bytes32 batchId,
        address recipient,
        uint256 amount,
        uint256 vintageYear,
        string calldata jurisdiction,
        string calldata methodology,
        bytes32 evidenceHash
    ) internal {
        if (recipient == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        uint256 serialNumber = totalIssued[uint256(keccak256(abi.encode(batchId, vintageYear)))];
        bytes32 tokenId = keccak256(abi.encode(batchId, vintageYear, recipient, serialNumber));

        if (_credits[uint256(tokenId)].batchId != bytes32(0)) {
            revert CreditAlreadyIssued(batchId, serialNumber);
        }

        _credits[uint256(tokenId)] = CreditRecord({
            batchId: batchId,
            vintageYear: vintageYear,
            locationId: recipient,
            serialNumber: serialNumber,
            jurisdiction: jurisdiction,
            methodology: methodology,
            evidenceHash: evidenceHash
        });

        totalIssued[uint256(tokenId)] += amount;
        batchExists[batchId] = true;

        _mint(recipient, uint256(tokenId), amount, "");

        emit CreditIssued(uint256(tokenId), batchId, recipient, amount, vintageYear, evidenceHash);
    }

    function retire(uint256 tokenId, uint256 amount, bytes32 reasonHash) external onlyRole(BURNER_ROLE) {
        if (amount == 0) revert ZeroAmount();

        uint256 available = totalIssued[tokenId] - totalRetired[tokenId];
        if (amount > available) revert InsufficientBalance(tokenId, amount, available);

        totalRetired[tokenId] += amount;
        _burn(msg.sender, tokenId, amount);

        if (totalRetired[tokenId] == totalIssued[tokenId]) {
            isRetired[tokenId] = true;
        }

        emit CreditRetired(tokenId, msg.sender, amount, reasonHash);
    }

    struct IssueParams {
        bytes32 batchId;
        address recipient;
        uint256 amount;
        uint256 vintageYear;
        string jurisdiction;
        string methodology;
        bytes32 evidenceHash;
    }

    function batchIssue(IssueParams[] calldata params) external onlyRole(ISSUER_ROLE) whenNotPaused {
        for (uint256 i = 0; i < params.length; i++) {
            IssueParams calldata p = params[i];
            _issue(p.batchId, p.recipient, p.amount, p.vintageYear, p.jurisdiction, p.methodology, p.evidenceHash);
        }
    }

    function getCreditInfo(uint256 tokenId) external view returns (CreditRecord memory) {
        return _credits[tokenId];
    }

    function availableBalance(uint256 tokenId) external view returns (uint256) {
        return totalIssued[tokenId] - totalRetired[tokenId];
    }

    function setApprovalForAll(address, bool) public pure override {
        revert NonTransferable();
    }

    function safeTransferFrom(address, address, uint256, uint256, bytes memory) public pure override {
        revert NonTransferable();
    }

    function safeBatchTransferFrom(address, address, uint256[] memory, uint256[] memory, bytes memory)
        public
        pure
        override
    {
        revert NonTransferable();
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    function setURI(string calldata newURI) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _setURI(newURI);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC1155Upgradeable, AccessControlUpgradeable)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    function _update(address from, address to, uint256[] memory ids, uint256[] memory values) internal override {
        if (from != address(0) && to != address(0)) revert NonTransferable();
        super._update(from, to, ids, values);
    }

    function _authorizeUpgrade(address) internal override onlyRole(UPGRADER_ROLE) {}
}
