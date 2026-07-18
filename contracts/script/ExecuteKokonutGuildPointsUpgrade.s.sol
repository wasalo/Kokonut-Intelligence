// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {KokonutGuildUpgradeTimelock} from "../src/KokonutGuildUpgradeTimelock.sol";

contract ExecuteKokonutGuildPointsUpgrade is Script {
    function run() external {
        address timelock = vm.envAddress("KGP_TIMELOCK");
        bytes32 upgradeId = vm.envBytes32("KGP_UPGRADE_ID");
        vm.startBroadcast();
        KokonutGuildUpgradeTimelock(timelock).executeUpgrade(upgradeId);
        vm.stopBroadcast();
        console.logBytes32(upgradeId);
    }
}
