// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {KokonutGuildUpgradeTimelock} from "../src/KokonutGuildUpgradeTimelock.sol";

contract ExecuteKokonutGuildPointsUpgrade is Script {
    uint256 private constant ANVIL_CHAIN_ID = 31337;
    uint256 private constant GNOSIS_CHAIN_ID = 100;
    uint256 private constant CHIADO_CHAIN_ID = 10200;

    function run() external {
        require(
            block.chainid == ANVIL_CHAIN_ID || block.chainid == GNOSIS_CHAIN_ID || block.chainid == CHIADO_CHAIN_ID,
            "Unsupported upgrade network"
        );
        address timelock = vm.envAddress("KGP_TIMELOCK");
        bytes32 upgradeId = vm.envBytes32("KGP_UPGRADE_ID");
        require(timelock.code.length > 0, "Invalid timelock address");
        vm.startBroadcast();
        KokonutGuildUpgradeTimelock(timelock).executeUpgrade(upgradeId);
        vm.stopBroadcast();
        console.logBytes32(upgradeId);
    }
}
