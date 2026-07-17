// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {Script, console} from "forge-std/Script.sol";
import {KokonutGuildPoints} from "../src/KokonutGuildPoints.sol";

/// @title UpgradeKokonutGuildPoints
/// @notice Deploys a new implementation and upgrades an existing UUPS proxy.
/// @dev The broadcast key must have UPGRADER_ROLE on the proxy.
contract UpgradeKokonutGuildPoints is Script {
    uint256 private constant GNOSIS_CHAIN_ID = 100;
    uint256 private constant CHIADO_CHAIN_ID = 10200;

    function run() external returns (address implementation) {
        require(block.chainid == GNOSIS_CHAIN_ID || block.chainid == CHIADO_CHAIN_ID, "Unsupported Gnosis network");

        uint256 upgraderKey = vm.envUint("KGP_UPGRADER_PRIVATE_KEY");
        address proxyAddress = vm.envAddress("KGP_PROXY");
        require(proxyAddress.code.length > 0, "KGP proxy has no deployed code");

        vm.startBroadcast(upgraderKey);
        KokonutGuildPoints newImplementation = new KokonutGuildPoints();
        KokonutGuildPoints(proxyAddress).upgradeToAndCall(address(newImplementation), "");
        vm.stopBroadcast();

        require(proxyAddress.code.length > 0, "KGP proxy code missing after upgrade");

        implementation = address(newImplementation);
        console.log("KokonutGuildPoints proxy:", proxyAddress);
        console.log("KokonutGuildPoints implementation:", implementation);
        console.log("Chain ID:", block.chainid);
    }
}
