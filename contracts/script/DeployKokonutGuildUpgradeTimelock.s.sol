// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {KokonutGuildUpgradeTimelock} from "../src/KokonutGuildUpgradeTimelock.sol";

/// @title DeployKokonutGuildUpgradeTimelock
/// @notice Deploys the KGP upgrade timelock after the KGP proxy exists.
contract DeployKokonutGuildUpgradeTimelock is Script {
    function run() external returns (KokonutGuildUpgradeTimelock timelock) {
        address deployer = vm.envAddress("KGP_DEPLOYER");
        address admin = vm.envAddress("KGP_ADMIN");
        address proposer = vm.envAddress("TIMELOCK_PROPOSER");
        address executor = vm.envAddress("TIMELOCK_EXECUTOR");
        address proxy = vm.envAddress("KGP_PROXY");
        uint256 delay = vm.envUint("KGP_TIMELOCK_DELAY");

        require(proxy.code.length > 0, "KGP proxy has no code");
        require(delay == 172800, "KGP timelock delay must be 48 hours");

        vm.startBroadcast();
        (, address broadcaster,) = vm.readCallers();
        require(broadcaster == deployer, "Deployer does not match broadcast sender");
        timelock = new KokonutGuildUpgradeTimelock(admin, proposer, executor, delay, proxy);
        vm.stopBroadcast();

        console.log("KGP timelock:", address(timelock));
        console.log("Approved proxy:", proxy);
        console.log("Delay:", delay);
        console.log("Admin:", admin);
        console.log("Proposer:", proposer);
        console.log("Executor:", executor);
    }
}
