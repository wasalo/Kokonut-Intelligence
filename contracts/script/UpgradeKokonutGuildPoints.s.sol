// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {KokonutGuildDomain} from "../src/KokonutGuildDomain.sol";
import {KokonutGuildPoints} from "../src/KokonutGuildPoints.sol";

/// @title UpgradeKokonutGuildPoints
/// @notice Deploys a new implementation and upgrades an existing UUPS proxy.
/// @dev Controlled local/test-only upgrade script. Production upgrades use the timelock scripts.
contract UpgradeKokonutGuildPoints is Script {
    uint256 private constant GNOSIS_CHAIN_ID = 100;
    uint256 private constant CHIADO_CHAIN_ID = 10200;

    function run() external returns (address implementation) {
        require(block.chainid == GNOSIS_CHAIN_ID || block.chainid == CHIADO_CHAIN_ID, "Unsupported Gnosis network");

        address proxyAddress = vm.envAddress("KGP_PROXY");
        implementation = vm.envAddress("KGP_IMPLEMENTATION");
        require(proxyAddress.code.length > 0 && implementation.code.length > 0, "Invalid upgrade addresses");
        string memory configuredData = vm.envOr("KGP_UPGRADE_DATA", string(""));
        bytes memory upgradeData;
        if (bytes(configuredData).length == 0) {
            KokonutGuildDomain domains = KokonutGuildDomain(vm.envAddress("KGP_DOMAIN_REGISTRY"));
            require(address(domains).code.length > 0, "Invalid domain registry");
            upgradeData = abi.encodeCall(KokonutGuildPoints.reinitializeDomainRegistry, (domains));
        } else {
            upgradeData = vm.parseBytes(configuredData);
        }

        vm.startBroadcast();
        KokonutGuildPoints(proxyAddress).upgradeToAndCall(implementation, upgradeData);
        vm.stopBroadcast();

        require(proxyAddress.code.length > 0, "KGP proxy code missing after upgrade");

        console.log("KokonutGuildPoints proxy:", proxyAddress);
        console.log("KokonutGuildPoints implementation:", implementation);
        console.log("Chain ID:", block.chainid);
    }
}
