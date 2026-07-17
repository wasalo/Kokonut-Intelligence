// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {KokonutGuildUpgradeTimelock} from "../src/KokonutGuildUpgradeTimelock.sol";

contract QueueKokonutGuildPointsUpgrade is Script {
    function run() external returns (bytes32 upgradeId) {
        address proxy = vm.envAddress("KGP_PROXY");
        address timelockAddress = vm.envAddress("KGP_TIMELOCK");
        address implementation = vm.envAddress("KGP_IMPLEMENTATION");
        require(proxy.code.length > 0 && implementation.code.length > 0, "Invalid upgrade addresses");

        vm.startBroadcast();
        upgradeId = KokonutGuildUpgradeTimelock(timelockAddress).queueUpgrade(proxy, implementation, "");
        vm.stopBroadcast();

        console.logBytes32(upgradeId);
        console.log("Implementation:", implementation);
    }
}
