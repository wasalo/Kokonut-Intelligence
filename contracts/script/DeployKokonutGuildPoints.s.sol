// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {KokonutGuildPoints} from "../src/KokonutGuildPoints.sol";

/// @title DeployKokonutGuildPoints
/// @notice Deploys the KGP implementation and UUPS proxy on Gnosis or Chiado.
/// @dev Required environment variables:
///   KGP_DEPLOYER, KGP_ADMIN, KGP_AWARDER, KGP_CLAIM_SIGNER,
///   KGP_REVERSER, KGP_PAUSER, KGP_UPGRADER.
///   Optional: KGP_URI (defaults to an immutable metadata placeholder).
contract DeployKokonutGuildPoints is Script {
    uint256 private constant GNOSIS_CHAIN_ID = 100;
    uint256 private constant CHIADO_CHAIN_ID = 10200;

    function run() external returns (KokonutGuildPoints points) {
        require(block.chainid == GNOSIS_CHAIN_ID || block.chainid == CHIADO_CHAIN_ID, "Unsupported Gnosis network");

        address deployer = vm.envAddress("KGP_DEPLOYER");
        address admin = vm.envAddress("KGP_ADMIN");
        address awarder = vm.envAddress("KGP_AWARDER");
        address claimSigner = vm.envAddress("KGP_CLAIM_SIGNER");
        address reverser = vm.envAddress("KGP_REVERSER");
        address pauser = vm.envAddress("KGP_PAUSER");
        address upgrader = vm.envAddress("KGP_UPGRADER");
        require(upgrader.code.length > 0, "KGP upgrader must be a timelock contract");
        require(
            deployer != address(0) && deployer != admin && deployer != awarder && deployer != claimSigner
                && deployer != reverser && deployer != pauser && deployer != upgrader,
            "KGP deployer cannot hold a privileged role"
        );
        string memory uri = vm.envOr("KGP_URI", string("ipfs://kokonut-kgp/{id}.json"));

        vm.startBroadcast();
        (, address broadcaster,) = vm.readCallers();
        require(broadcaster == deployer, "Deployer does not match broadcast sender");
        KokonutGuildPoints implementation = new KokonutGuildPoints();
        bytes memory initialization = abi.encodeCall(
            KokonutGuildPoints.initialize, (admin, awarder, claimSigner, reverser, pauser, upgrader, uri)
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(implementation), initialization);
        vm.stopBroadcast();

        points = KokonutGuildPoints(address(proxy));
        console.log("KokonutGuildPoints proxy:", address(points));
        console.log("KokonutGuildPoints implementation:", address(implementation));
        console.log("Chain ID:", block.chainid);
        console.log("Admin:", admin);
        console.log("Awarder:", awarder);
        console.log("Claim signer:", claimSigner);
        console.log("Reverser:", reverser);
        console.log("Pauser:", pauser);
        console.log("Upgrader:", upgrader);
    }
}
