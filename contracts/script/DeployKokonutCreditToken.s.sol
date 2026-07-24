// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {KokonutCreditToken} from "../src/KokonutCreditToken.sol";
import {ERC1155Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC1155/ERC1155Upgradeable.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import {ProxyAdmin} from "@openzeppelin/contracts/proxy/transparent/ProxyAdmin.sol";

contract DeployKokonutCreditToken is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address admin = vm.envAddress("ADMIN_ADDRESS");
        address issuer = vm.envAddress("ISSUER_ADDRESS");
        address burner = vm.envAddress("BURNER_ADDRESS");
        address pauser = vm.envAddress("PAUSER_ADDRESS");
        address upgrader = vm.envAddress("UPGRADER_ADDRESS");
        string memory uri = vm.envOr("TOKEN_URI", string("https://api.kokonut.network/credit-tokens/{id}.json"));

        vm.startBroadcast(deployerPrivateKey);

        console.log("Deploying KokonutCreditToken implementation...");
        KokonutCreditToken impl = new KokonutCreditToken();

        console.log("Deploying ProxyAdmin...");
        ProxyAdmin proxyAdmin = new ProxyAdmin(admin);

        console.log("Deploying proxy...");
        TransparentUpgradeableProxy proxy = new TransparentUpgradeableProxy(
            address(impl),
            address(proxyAdmin),
            abi.encodeCall(
                KokonutCreditToken.initialize,
                (admin, issuer, burner, pauser, upgrader, uri)
            )
        );

        console.log("KokonutCreditToken deployed at:", address(proxy));
        console.log("ProxyAdmin at:", address(proxyAdmin));
        console.log("Implementation at:", address(impl));

        vm.stopBroadcast();
    }
}
