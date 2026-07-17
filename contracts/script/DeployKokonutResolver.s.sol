// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {Script, console} from "forge-std/Script.sol";
import {KokonutResolver} from "../src/KokonutResolver.sol";
import {IEAS} from "@eas-contracts/IEAS.sol";

/// @title DeployKokonutResolver
/// @notice Deploy script for KokonutResolver on Celo or any EAS-supported chain.
/// @dev Usage:
///   CELO_RPC_URL=... ATTESTER_PRIVATE_KEY=... forge script script/DeployKokonutResolver.s.sol \
///     --rpc-url $CELO_RPC_URL --broadcast --verify
contract DeployKokonutResolver is Script {
    // Celo mainnet EAS address
    address constant CELO_EAS = 0x72E1d8ccf5299fb36fEfD8CC4394B8ef7e98Af92;
    // Kokonut multisig
    address constant KOKONUT_MULTISIG = 0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5;

    function run() external returns (KokonutResolver resolver) {
        uint256 deployerKey = vm.envUint("ATTESTER_PRIVATE_KEY");
        address deployer = vm.addr(deployerKey);
        address easAddress = vm.envOr("EAS_ADDRESS", CELO_EAS);

        address[] memory initialAttesters = new address[](1);
        initialAttesters[0] = KOKONUT_MULTISIG;

        vm.startBroadcast(deployerKey);
        resolver = new KokonutResolver(IEAS(easAddress), KOKONUT_MULTISIG, initialAttesters);
        vm.stopBroadcast();

        require(resolver.owner() == KOKONUT_MULTISIG, "Resolver ownership handoff failed");

        console.log("KokonutResolver deployed at:", address(resolver));
        console.log("Owner:", KOKONUT_MULTISIG);
        console.log("EAS:", easAddress);
        console.log("Allowed attesters:");
        console.log("  - Deployer:", deployer);
        console.log("  - Kokonut Multisig:", KOKONUT_MULTISIG);
    }
}
