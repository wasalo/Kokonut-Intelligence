// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {Script, console} from "forge-std/Script.sol";
import {KokonutGuildPoints} from "../src/KokonutGuildPoints.sol";
import {KokonutGuildUpgradeTimelock} from "../src/KokonutGuildUpgradeTimelock.sol";

contract QueueKokonutGuildPointsUpgrade is Script {
    function run() external returns (bytes32 upgradeId) {
        address proxy = vm.envAddress("KGP_PROXY");
        address timelockAddress = vm.envAddress("KGP_TIMELOCK");
        uint256 deployerKey = vm.envUint("KGP_IMPLEMENTATION_DEPLOYER_PRIVATE_KEY");
        uint256 proposerKey = vm.envUint("KGP_TIMELOCK_PROPOSER_PRIVATE_KEY");

        vm.startBroadcast(deployerKey);
        KokonutGuildPoints implementation = new KokonutGuildPoints();
        vm.stopBroadcast();

        vm.startBroadcast(proposerKey);
        upgradeId = KokonutGuildUpgradeTimelock(timelockAddress).queueUpgrade(proxy, address(implementation), "");
        vm.stopBroadcast();

        console.logBytes32(upgradeId);
        console.log("Implementation:", address(implementation));
    }
}
