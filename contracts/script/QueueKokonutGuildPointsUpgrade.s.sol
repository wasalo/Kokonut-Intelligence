// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {KokonutGuildDomain} from "../src/KokonutGuildDomain.sol";
import {KokonutGuildPoints} from "../src/KokonutGuildPoints.sol";
import {KokonutGuildUpgradeTimelock} from "../src/KokonutGuildUpgradeTimelock.sol";

contract QueueKokonutGuildPointsUpgrade is Script {
    uint256 private constant ANVIL_CHAIN_ID = 31337;
    uint256 private constant GNOSIS_CHAIN_ID = 100;
    uint256 private constant CHIADO_CHAIN_ID = 10200;

    function run() external returns (bytes32 upgradeId) {
        require(
            block.chainid == ANVIL_CHAIN_ID || block.chainid == GNOSIS_CHAIN_ID || block.chainid == CHIADO_CHAIN_ID,
            "Unsupported upgrade network"
        );
        address proxy = vm.envAddress("KGP_PROXY");
        address timelockAddress = vm.envAddress("KGP_TIMELOCK");
        address implementation = vm.envAddress("KGP_IMPLEMENTATION");
        require(
            proxy.code.length > 0 && implementation.code.length > 0 && timelockAddress.code.length > 0,
            "Invalid upgrade addresses"
        );
        require(KokonutGuildUpgradeTimelock(timelockAddress).approvedProxy() == proxy, "Timelock proxy mismatch");

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
        upgradeId = KokonutGuildUpgradeTimelock(timelockAddress).queueUpgrade(proxy, implementation, upgradeData);
        vm.stopBroadcast();

        console.logBytes32(upgradeId);
        console.log("Implementation:", implementation);
    }
}
