// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {KokonutGuildDomain} from "../src/KokonutGuildDomain.sol";
import {KokonutGuildPoints} from "../src/KokonutGuildPoints.sol";
import {KokonutGuildUpgradeTimelock} from "../src/KokonutGuildUpgradeTimelock.sol";

contract QueueKokonutGuildPointsUpgrade is Script {
    function run() external returns (bytes32 upgradeId) {
        address proxy = vm.envAddress("KGP_PROXY");
        address timelockAddress = vm.envAddress("KGP_TIMELOCK");
        address implementation = vm.envAddress("KGP_IMPLEMENTATION");
        require(proxy.code.length > 0 && implementation.code.length > 0, "Invalid upgrade addresses");
        require(KokonutGuildUpgradeTimelock(timelockAddress).approvedProxy() == proxy, "Timelock proxy mismatch");

        string memory configuredData = vm.envOr("KGP_UPGRADE_DATA", string(""));
        bytes memory upgradeData;
        if (bytes(configuredData).length == 0) {
            KokonutGuildDomain domains = KokonutGuildDomain(vm.envAddress("KGP_DOMAIN_REGISTRY"));
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
