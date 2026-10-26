// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {KokonutSelectiveDisclosure} from "../src/KokonutSelectiveDisclosure.sol";

contract KokonutSelectiveDisclosureTest is Test {
    KokonutSelectiveDisclosure public disclosure;
    address public admin = makeAddr("admin");
    address public attester = makeAddr("attester");
    address public pauser = makeAddr("pauser");
    address public upgrader = makeAddr("upgrader");

    bytes32 constant ATTESTATION_UID = keccak256("attestation-001");
    bytes32 constant ROOT = keccak256("merkle-root-001");

    function setUp() public {
        KokonutSelectiveDisclosure impl = new KokonutSelectiveDisclosure();
        bytes memory init = abi.encodeCall(KokonutSelectiveDisclosure.initialize, (admin, attester, pauser, upgrader));
        ERC1967Proxy proxy = new ERC1967Proxy(address(impl), init);
        disclosure = KokonutSelectiveDisclosure(address(proxy));
    }

    function testSetRoot() public {
        vm.prank(attester);
        disclosure.setRoot(ATTESTATION_UID, ROOT);

        assertEq(disclosure.disclosureRoots(ATTESTATION_UID), ROOT);
        assertTrue(disclosure.isSet(ATTESTATION_UID));
    }

    function testSetRootRevertsOnUnauthorized() public {
        vm.prank(makeAddr("unauthorized"));
        vm.expectRevert();
        disclosure.setRoot(ATTESTATION_UID, ROOT);
    }

    function testSetRootRevertsOnDuplicate() public {
        vm.prank(attester);
        disclosure.setRoot(ATTESTATION_UID, ROOT);

        vm.prank(attester);
        vm.expectRevert();
        disclosure.setRoot(ATTESTATION_UID, ROOT);
    }

    function testVerifyProof() public {
        bytes32 leaf = keccak256("leaf-data");
        bytes32[] memory proof = new bytes32[](2);
        proof[0] = keccak256("sibling-1");
        proof[1] = keccak256("sibling-2");
        uint8[] memory flags = new uint8[](2);
        flags[0] = 0;
        flags[1] = 1;

        bytes32 computed = leaf;
        computed = keccak256(abi.encodePacked(computed, proof[0]));
        computed = keccak256(abi.encodePacked(proof[1], computed));

        vm.prank(attester);
        disclosure.setRoot(ATTESTATION_UID, computed);

        assertTrue(disclosure.verifyProof(ATTESTATION_UID, leaf, proof, flags));
    }

    function testVerifyProofReturnsFalseForInvalidRoot() public view {
        bytes32 leaf = keccak256("leaf-data");
        bytes32[] memory proof = new bytes32[](0);
        uint8[] memory flags = new uint8[](0);

        assertFalse(disclosure.verifyProof(ATTESTATION_UID, leaf, proof, flags));
    }

    function testVerifyProofReturnsFalseForMismatchedProofAndFlagLengths() public {
        bytes32 leaf = keccak256("leaf-data");
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256("sibling");
        uint8[] memory flags = new uint8[](0);
        bytes32 root = keccak256(abi.encodePacked(leaf, proof[0]));

        vm.prank(attester);
        disclosure.setRoot(ATTESTATION_UID, root);

        assertFalse(disclosure.verifyProof(ATTESTATION_UID, leaf, proof, flags));
    }

    function testVerifyProofReturnsFalseForUnsupportedFlag() public {
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256("sibling");
        uint8[] memory flags = new uint8[](1);
        flags[0] = 2;

        vm.prank(attester);
        disclosure.setRoot(ATTESTATION_UID, ROOT);

        assertFalse(disclosure.verifyProof(ATTESTATION_UID, keccak256("leaf-data"), proof, flags));
    }

    function testFuzz_VerifyProofRejectsUnsupportedFlag(uint8 flagInput) public {
        uint8 invalidFlag = uint8(bound(flagInput, 2, type(uint8).max));
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256("sibling");
        uint8[] memory flags = new uint8[](1);
        flags[0] = invalidFlag;

        vm.prank(attester);
        disclosure.setRoot(ATTESTATION_UID, ROOT);

        assertFalse(disclosure.verifyProof(ATTESTATION_UID, keccak256("leaf-data"), proof, flags));
    }

    function testVerifyProofReturnsFalseForWrongLeaf() public {
        bytes32 leaf = keccak256("leaf-data");
        bytes32 sibling = keccak256("sibling");
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = sibling;
        uint8[] memory flags = new uint8[](1);
        flags[0] = 0;

        vm.prank(attester);
        disclosure.setRoot(ATTESTATION_UID, keccak256(abi.encodePacked(leaf, sibling)));

        assertFalse(disclosure.verifyProof(ATTESTATION_UID, keccak256("different-leaf"), proof, flags));
    }

    function testPause() public {
        vm.prank(pauser);
        disclosure.pause();

        vm.prank(attester);
        vm.expectRevert();
        disclosure.setRoot(ATTESTATION_UID, ROOT);

        vm.prank(pauser);
        disclosure.unpause();

        vm.prank(attester);
        disclosure.setRoot(ATTESTATION_UID, ROOT);
    }
}
