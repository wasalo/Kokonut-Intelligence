// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {Test} from "forge-std/Test.sol";
import {KokonutResolver} from "../src/KokonutResolver.sol";
import {IEAS} from "@eas-contracts/IEAS.sol";

contract KokonutResolverTest is Test {
    KokonutResolver public resolver;
    address public owner = address(0x1);
    address public attester1 = address(0x2);
    address public attester2 = address(0x3);
    address public unauthorized = address(0x4);
    address public easMock = address(0x5);

    function setUp() public {
        address[] memory attesters = new address[](2);
        attesters[0] = attester1;
        attesters[1] = attester2;
        resolver = new KokonutResolver(
            IEAS(easMock),
            owner,
            attesters
        );
    }

    function test_initial_attesters_allowed() public view {
        assertTrue(resolver.allowedAttesters(attester1));
        assertTrue(resolver.allowedAttesters(attester2));
        assertFalse(resolver.allowedAttesters(unauthorized));
    }

    function test_owner_can_add_attester() public {
        vm.prank(owner);
        resolver.addAttester(unauthorized);
        assertTrue(resolver.allowedAttesters(unauthorized));
    }

    function test_owner_can_remove_attester() public {
        vm.prank(owner);
        resolver.removeAttester(attester1);
        assertFalse(resolver.allowedAttesters(attester1));
    }

    function test_non_owner_cannot_add_attester() public {
        vm.prank(unauthorized);
        vm.expectRevert();
        resolver.addAttester(address(0x99));
    }

    function test_non_owner_cannot_remove_attester() public {
        vm.prank(unauthorized);
        vm.expectRevert();
        resolver.removeAttester(attester1);
    }

    function test_cannot_add_zero_address() public {
        vm.prank(owner);
        vm.expectRevert("Zero address");
        resolver.addAttester(address(0));
    }

    function test_is_payable_returns_false() public view {
        assertFalse(resolver.isPayable());
    }

    function test_fuzz_add_remove_attester(address attester) public {
        vm.assume(attester != address(0));

        vm.prank(owner);
        resolver.addAttester(attester);
        assertTrue(resolver.allowedAttesters(attester));

        vm.prank(owner);
        resolver.removeAttester(attester);
        assertFalse(resolver.allowedAttesters(attester));
    }
}
