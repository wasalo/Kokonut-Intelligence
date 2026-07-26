// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {KokonutPriceOracle} from "../src/KokonutPriceOracle.sol";
import {KokonutSelectiveDisclosure} from "../src/KokonutSelectiveDisclosure.sol";

/// @title DeployKokonutInfrastructure
/// @notice Deploys the Selective Disclosure and Price Oracle UUPS proxies.
contract DeployKokonutInfrastructure is Script {
    struct Config {
        address deployer;
        address admin;
        address selectiveAttester;
        address selectivePauser;
        address selectiveUpgrader;
        address oracleUpdater;
        address oraclePauser;
        address oracleUpgrader;
    }

    function run() external returns (KokonutSelectiveDisclosure disclosure, KokonutPriceOracle oracle) {
        Config memory config = _readConfig();

        vm.startBroadcast();
        (, address broadcaster,) = vm.readCallers();
        require(broadcaster == config.deployer, "Deployer does not match broadcast sender");

        KokonutSelectiveDisclosure disclosureImplementation = new KokonutSelectiveDisclosure();
        ERC1967Proxy disclosureProxy = new ERC1967Proxy(
            address(disclosureImplementation),
            abi.encodeCall(
                KokonutSelectiveDisclosure.initialize,
                (config.admin, config.selectiveAttester, config.selectivePauser, config.selectiveUpgrader)
            )
        );

        KokonutPriceOracle oracleImplementation = new KokonutPriceOracle();
        ERC1967Proxy oracleProxy = new ERC1967Proxy(
            address(oracleImplementation),
            abi.encodeCall(
                KokonutPriceOracle.initialize,
                (config.admin, config.oracleUpdater, config.oraclePauser, config.oracleUpgrader)
            )
        );
        vm.stopBroadcast();

        disclosure = KokonutSelectiveDisclosure(address(disclosureProxy));
        oracle = KokonutPriceOracle(address(oracleProxy));
        console.log("Selective Disclosure proxy:", address(disclosure));
        console.log("Selective Disclosure implementation:", address(disclosureImplementation));
        console.log("Price Oracle proxy:", address(oracle));
        console.log("Price Oracle implementation:", address(oracleImplementation));
        console.log("Chain ID:", block.chainid);
    }

    function _readConfig() internal view returns (Config memory config) {
        config.deployer = vm.envAddress("INFRA_DEPLOYER");
        config.admin = vm.envAddress("SELECTIVE_DISCLOSURE_ADMIN");
        require(config.admin == vm.envAddress("PRICE_ORACLE_ADMIN"), "Infrastructure admins must match");
        config.selectiveAttester = vm.envAddress("SELECTIVE_DISCLOSURE_ATTESTER");
        config.selectivePauser = vm.envAddress("SELECTIVE_DISCLOSURE_PAUSER");
        config.selectiveUpgrader = vm.envAddress("SELECTIVE_DISCLOSURE_UPGRADER");
        config.oracleUpdater = vm.envAddress("PRICE_ORACLE_UPDATER");
        config.oraclePauser = vm.envAddress("PRICE_ORACLE_PAUSER");
        config.oracleUpgrader = vm.envAddress("PRICE_ORACLE_UPGRADER");
    }
}
