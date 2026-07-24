// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {KokonutPriceOracle} from "../src/KokonutPriceOracle.sol";

contract KokonutPriceOracleTest is Test {
    KokonutPriceOracle public oracle;
    address public admin = makeAddr("admin");
    address public updater = makeAddr("updater");
    address public pauser = makeAddr("pauser");
    address public upgrader = makeAddr("upgrader");

    bytes32 constant FEED_KEY = keccak256("maize-KE");
    bytes32 constant ATTESTATION_UID = keccak256("att-001");
    bytes32 constant SOURCE = keccak256("world-bank");

    function setUp() public {
        KokonutPriceOracle impl = new KokonutPriceOracle();
        bytes memory init = abi.encodeCall(
            KokonutPriceOracle.initialize,
            (admin, updater, pauser, upgrader)
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(impl), init);
        oracle = KokonutPriceOracle(address(proxy));
    }

    function testUpdatePrice() public {
        vm.prank(updater);
        oracle.updatePrice(FEED_KEY, 250000, "world-bank", ATTESTATION_UID, 95);

        KokonutPriceOracle.PriceFeed memory feed = oracle.getPrice(FEED_KEY);
        assertEq(feed.price, 250000);
        assertEq(feed.confidence, 95);
        assertEq(feed.updateCount, 1);
        assertTrue(feed.timestamp > 0);
    }

    function testUpdatePriceRevertsOnZero() public {
        vm.prank(updater);
        vm.expectRevert(KokonutPriceOracle.ZeroPrice.selector);
        oracle.updatePrice(FEED_KEY, 0, "world-bank", ATTESTATION_UID, 95);
    }

    function testUpdatePriceRevertsOnUnauthorized() public {
        vm.prank(makeAddr("unauthorized"));
        vm.expectRevert();
        oracle.updatePrice(FEED_KEY, 250000, "world-bank", ATTESTATION_UID, 95);
    }

    function testConfidenceThreshold() public {
        vm.prank(updater);
        oracle.setConfidenceThreshold(FEED_KEY, 80);

        vm.prank(updater);
        vm.expectRevert();
        oracle.updatePrice(FEED_KEY, 250000, "world-bank", ATTESTATION_UID, 70);

        vm.prank(updater);
        oracle.updatePrice(FEED_KEY, 250000, "world-bank", ATTESTATION_UID, 80);
    }

    function testPriceHistory() public {
        vm.startPrank(updater);
        oracle.updatePrice(FEED_KEY, 250000, "world-bank", ATTESTATION_UID, 95);
        oracle.updatePrice(FEED_KEY, 260000, "world-bank", ATTESTATION_UID, 90);
        vm.stopPrank();

        KokonutPriceOracle.PriceHistoryEntry[] memory history = oracle.getPriceHistory(FEED_KEY, 10);
        assertEq(history.length, 2);
        assertEq(history[0].price, 250000);
        assertEq(history[1].price, 260000);
    }

    function testFeedExists() public {
        assertFalse(oracle.feedExists(FEED_KEY));

        vm.prank(updater);
        oracle.updatePrice(FEED_KEY, 250000, "world-bank", ATTESTATION_UID, 95);

        assertTrue(oracle.feedExists(FEED_KEY));
    }

    function testPause() public {
        vm.prank(pauser);
        oracle.pause();

        vm.prank(updater);
        vm.expectRevert();
        oracle.updatePrice(FEED_KEY, 250000, "world-bank", ATTESTATION_UID, 95);

        vm.prank(pauser);
        oracle.unpause();

        vm.prank(updater);
        oracle.updatePrice(FEED_KEY, 250000, "world-bank", ATTESTATION_UID, 95);
    }
}
