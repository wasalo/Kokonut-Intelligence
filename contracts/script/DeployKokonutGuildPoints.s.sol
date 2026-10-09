// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {KokonutGuildPoints} from "../src/KokonutGuildPoints.sol";
import {KokonutGuildDomain} from "../src/KokonutGuildDomain.sol";

/// @title DeployKokonutGuildPoints
/// @notice Deploys the KGP implementation and UUPS proxy on Gnosis or Chiado.
/// @dev Required environment variables:
///   KGP_DEPLOYER, KGP_ADMIN, KGP_AWARDER, KGP_CLAIM_SIGNER,
///   KGP_REVERSER, KGP_PAUSER, KGP_UPGRADER, KGP_DOMAIN_REGISTRY.
///   Optional: KGP_URI (defaults to an immutable metadata placeholder).
contract DeployKokonutGuildPoints is Script {
    uint256 private constant GNOSIS_CHAIN_ID = 100;
    uint256 private constant CHIADO_CHAIN_ID = 10200;

    struct Config {
        address deployer;
        address admin;
        address awarder;
        address claimSigner;
        address reverser;
        address pauser;
        address upgrader;
        address domainRegistry;
        string uri;
    }

    function run() external returns (KokonutGuildPoints points) {
        require(block.chainid == GNOSIS_CHAIN_ID || block.chainid == CHIADO_CHAIN_ID, "Unsupported Gnosis network");

        Config memory config = _readConfig();
        KokonutGuildDomain domains = KokonutGuildDomain(config.domainRegistry);
        bool temporaryUpgrader = vm.envOr("KGP_ALLOW_TEMPORARY_UPGRADER", false);
        require(temporaryUpgrader || config.upgrader.code.length > 0, "KGP upgrader must be a timelock contract");
        if (temporaryUpgrader) {
            require(config.upgrader != address(0) && config.upgrader != config.admin, "Invalid temporary KGP upgrader");
        }
        require(config.domainRegistry.code.length > 0, "KGP domain registry has no code");
        require(address(domains.registry()).code.length > 0, "KGP Guild registry has no code");
        require(
            config.deployer != address(0) && config.deployer != config.admin && config.deployer != config.awarder
                && config.deployer != config.claimSigner && config.deployer != config.reverser
                && config.deployer != config.pauser && config.deployer != config.upgrader,
            "KGP deployer cannot hold a privileged role"
        );

        vm.startBroadcast();
        (, address broadcaster,) = vm.readCallers();
        require(broadcaster == config.deployer, "Deployer does not match broadcast sender");
        KokonutGuildPoints implementation = new KokonutGuildPoints();
        bytes memory initialization = abi.encodeCall(
            KokonutGuildPoints.initialize,
            (
                config.admin,
                config.awarder,
                config.claimSigner,
                config.reverser,
                config.pauser,
                config.upgrader,
                domains,
                config.uri
            )
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(implementation), initialization);
        vm.stopBroadcast();

        points = KokonutGuildPoints(address(proxy));
        console.log("KokonutGuildPoints proxy:", address(points));
        console.log("KokonutGuildPoints implementation:", address(implementation));
        console.log("Chain ID:", block.chainid);
        console.log("Admin:", config.admin);
        console.log("Awarder:", config.awarder);
        console.log("Claim signer:", config.claimSigner);
        console.log("Reverser:", config.reverser);
        console.log("Pauser:", config.pauser);
        console.log("Upgrader:", config.upgrader);
    }

    function _readConfig() internal view returns (Config memory config) {
        config.deployer = vm.envAddress("KGP_DEPLOYER");
        config.admin = vm.envAddress("KGP_ADMIN");
        config.awarder = vm.envAddress("KGP_AWARDER");
        config.claimSigner = vm.envAddress("KGP_CLAIM_SIGNER");
        config.reverser = vm.envAddress("KGP_REVERSER");
        config.pauser = vm.envAddress("KGP_PAUSER");
        config.upgrader = vm.envAddress("KGP_UPGRADER");
        config.domainRegistry = vm.envAddress("KGP_DOMAIN_REGISTRY");
        config.uri = vm.envOr("KGP_URI", string("ipfs://kokonut-kgp/{id}.json"));
    }
}
