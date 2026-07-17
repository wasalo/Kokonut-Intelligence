// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {EIP712Upgradeable} from "@openzeppelin/contracts-upgradeable/utils/cryptography/EIP712Upgradeable.sol";
import {ERC1155Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC1155/ERC1155Upgradeable.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/// @title Kokonut Guild Points
/// @notice Non-transferable, domain-scoped reputation points.
/// @dev PostgreSQL is the canonical governed ledger. This contract records an
///      auditable, idempotent projection of accepted awards and reversals.
contract KokonutGuildPoints is
    Initializable,
    ERC1155Upgradeable,
    AccessControlUpgradeable,
    EIP712Upgradeable,
    UUPSUpgradeable,
    PausableUpgradeable
{
    bytes32 public constant AWARDER_ROLE = keccak256("AWARDER_ROLE");
    bytes32 public constant CLAIM_SIGNER_ROLE = keccak256("CLAIM_SIGNER_ROLE");
    bytes32 public constant REVERSER_ROLE = keccak256("REVERSER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    bytes32 public constant CLAIM_VOUCHER_TYPEHASH = keccak256(
        "ClaimVoucher(bytes32 awardId,bytes32 guildId,address contributor,uint256 domainId,uint256 amount,uint256 epoch,bytes32 evidenceHash,bytes32 ledgerRecordHash,bytes32 calculationVersion,uint256 nonce,uint48 deadline)"
    );

    error ZeroAddress();
    error ZeroAmount();
    error AwardAlreadySettled(bytes32 awardId);
    error ReversalAlreadySettled(bytes32 reversalId);
    error UnknownAward(bytes32 awardId);
    error AwardMismatch(bytes32 awardId);
    error ExcessiveReversal(bytes32 awardId, uint256 requested, uint256 outstanding);
    error ClaimExpired(uint48 deadline);
    error ClaimSenderMismatch(address expected, address actual);
    error ClaimNonceUsed(address contributor, uint256 nonce);
    error InvalidClaimSigner(address signer);
    error NonTransferable();

    struct AwardRecord {
        bytes32 guildId;
        address contributor;
        uint256 domainId;
        uint256 amount;
        uint256 outstanding;
        uint256 epoch;
        bytes32 evidenceHash;
        bytes32 ledgerRecordHash;
        bytes32 calculationVersion;
    }

    struct ClaimVoucher {
        bytes32 awardId;
        bytes32 guildId;
        address contributor;
        uint256 domainId;
        uint256 amount;
        uint256 epoch;
        bytes32 evidenceHash;
        bytes32 ledgerRecordHash;
        bytes32 calculationVersion;
        uint256 nonce;
        uint48 deadline;
    }

    mapping(bytes32 awardId => AwardRecord record) private _awards;
    mapping(bytes32 reversalId => bool settled) public settledReversals;
    mapping(address contributor => mapping(uint256 nonce => bool used)) public usedClaimNonces;

    event KGP_Awarded(
        bytes32 indexed awardId,
        bytes32 indexed guildId,
        address indexed contributor,
        uint256 domainId,
        uint256 amount,
        uint256 epoch,
        bytes32 evidenceHash,
        bytes32 ledgerRecordHash,
        bytes32 calculationVersion
    );
    event KGPClaimed(bytes32 indexed awardId, address indexed contributor, uint256 nonce);
    event KGPReversed(
        bytes32 indexed reversalId,
        bytes32 indexed awardId,
        bytes32 indexed guildId,
        address contributor,
        uint256 domainId,
        uint256 amount,
        bytes32 reasonHash,
        bytes32 ledgerRecordHash,
        bytes32 calculationVersion
    );
    event URIUpdated(string value);

    constructor() {
        _disableInitializers();
    }

    function initialize(
        address admin,
        address awarder,
        address claimSigner,
        address reverser,
        address pauser,
        address upgrader,
        string calldata initialURI
    ) external initializer {
        if (
            admin == address(0) || awarder == address(0) || claimSigner == address(0) || reverser == address(0)
                || pauser == address(0) || upgrader == address(0)
        ) {
            revert ZeroAddress();
        }

        __ERC1155_init(initialURI);
        __AccessControl_init();
        __EIP712_init("Kokonut Guild Points", "1");
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(AWARDER_ROLE, awarder);
        _grantRole(CLAIM_SIGNER_ROLE, claimSigner);
        _grantRole(REVERSER_ROLE, reverser);
        _grantRole(PAUSER_ROLE, pauser);
        _grantRole(UPGRADER_ROLE, upgrader);
    }

    function award(
        bytes32 awardId,
        bytes32 guildId,
        address contributor,
        uint256 domainId,
        uint256 amount,
        uint256 epoch,
        bytes32 evidenceHash,
        bytes32 ledgerRecordHash,
        bytes32 calculationVersion
    ) external onlyRole(AWARDER_ROLE) whenNotPaused {
        _settleAward(
            awardId, guildId, contributor, domainId, amount, epoch, evidenceHash, ledgerRecordHash, calculationVersion
        );
    }

    function claim(ClaimVoucher calldata voucher, bytes calldata signature) external whenNotPaused {
        if (block.timestamp > voucher.deadline) revert ClaimExpired(voucher.deadline);
        if (msg.sender != voucher.contributor) revert ClaimSenderMismatch(voucher.contributor, msg.sender);
        if (usedClaimNonces[voucher.contributor][voucher.nonce]) {
            revert ClaimNonceUsed(voucher.contributor, voucher.nonce);
        }

        address signer = ECDSA.recover(claimDigest(voucher), signature);
        if (!hasRole(CLAIM_SIGNER_ROLE, signer)) revert InvalidClaimSigner(signer);

        usedClaimNonces[voucher.contributor][voucher.nonce] = true;
        _settleAward(
            voucher.awardId,
            voucher.guildId,
            voucher.contributor,
            voucher.domainId,
            voucher.amount,
            voucher.epoch,
            voucher.evidenceHash,
            voucher.ledgerRecordHash,
            voucher.calculationVersion
        );
        emit KGPClaimed(voucher.awardId, voucher.contributor, voucher.nonce);
    }

    function reverseAward(
        bytes32 reversalId,
        bytes32 awardId,
        uint256 amount,
        bytes32 reasonHash,
        bytes32 ledgerRecordHash,
        bytes32 calculationVersion
    ) external onlyRole(REVERSER_ROLE) whenNotPaused {
        if (settledReversals[reversalId]) revert ReversalAlreadySettled(reversalId);

        AwardRecord storage record = _awards[awardId];
        if (record.contributor == address(0)) revert UnknownAward(awardId);
        if (amount == 0) revert ZeroAmount();
        if (amount > record.outstanding) revert ExcessiveReversal(awardId, amount, record.outstanding);

        settledReversals[reversalId] = true;
        record.outstanding -= amount;
        _burn(record.contributor, record.domainId, amount);

        emit KGPReversed(
            reversalId,
            awardId,
            record.guildId,
            record.contributor,
            record.domainId,
            amount,
            reasonHash,
            ledgerRecordHash,
            calculationVersion
        );
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    function setURI(string calldata newURI) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _setURI(newURI);
        emit URI(newURI, 0);
        emit URIUpdated(newURI);
    }

    function getAward(bytes32 awardId) external view returns (AwardRecord memory) {
        return _awards[awardId];
    }

    function isAwardSettled(bytes32 awardId) external view returns (bool) {
        return _awards[awardId].contributor != address(0);
    }

    function claimDigest(ClaimVoucher calldata voucher) public view returns (bytes32) {
        return _hashTypedDataV4(
            keccak256(
                abi.encode(
                    CLAIM_VOUCHER_TYPEHASH,
                    voucher.awardId,
                    voucher.guildId,
                    voucher.contributor,
                    voucher.domainId,
                    voucher.amount,
                    voucher.epoch,
                    voucher.evidenceHash,
                    voucher.ledgerRecordHash,
                    voucher.calculationVersion,
                    voucher.nonce,
                    voucher.deadline
                )
            )
        );
    }

    function computeAwardId(
        bytes32 guildId,
        uint256 domainId,
        address contributor,
        bytes32 ledgerEventId,
        bytes32 calculationVersion
    ) external pure returns (bytes32) {
        return keccak256(abi.encode(guildId, domainId, contributor, ledgerEventId, calculationVersion));
    }

    function domainBalance(address contributor, uint256 domainId) external view returns (uint256) {
        return balanceOf(contributor, domainId);
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

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC1155Upgradeable, AccessControlUpgradeable)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    function _settleAward(
        bytes32 awardId,
        bytes32 guildId,
        address contributor,
        uint256 domainId,
        uint256 amount,
        uint256 epoch,
        bytes32 evidenceHash,
        bytes32 ledgerRecordHash,
        bytes32 calculationVersion
    ) internal {
        if (_awards[awardId].contributor != address(0)) revert AwardAlreadySettled(awardId);
        if (contributor == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        _awards[awardId] = AwardRecord({
            guildId: guildId,
            contributor: contributor,
            domainId: domainId,
            amount: amount,
            outstanding: amount,
            epoch: epoch,
            evidenceHash: evidenceHash,
            ledgerRecordHash: ledgerRecordHash,
            calculationVersion: calculationVersion
        });
        _mint(contributor, domainId, amount, "");

        emit KGP_Awarded(
            awardId, guildId, contributor, domainId, amount, epoch, evidenceHash, ledgerRecordHash, calculationVersion
        );
    }

    function _update(address from, address to, uint256[] memory ids, uint256[] memory values) internal override {
        if (from != address(0) && to != address(0)) revert NonTransferable();
        super._update(from, to, ids, values);
    }

    function _authorizeUpgrade(address) internal override onlyRole(UPGRADER_ROLE) {}
}
