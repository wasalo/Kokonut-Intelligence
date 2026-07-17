// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {Script, console} from "forge-std/Script.sol";
import {KokonutEvidenceReview} from "../src/KokonutEvidenceReview.sol";
import {KokonutGuildDomain} from "../src/KokonutGuildDomain.sol";
import {KokonutGuildGovernance} from "../src/KokonutGuildGovernance.sol";
import {KokonutGuildRegistry} from "../src/KokonutGuildRegistry.sol";
import {KokonutTaskBoard} from "../src/KokonutTaskBoard.sol";

/// @title DeployKokonutGuildProtocol
/// @notice Deploys and wires the operational Guild protocol contracts.
/// @dev Required: GUILD_PROTOCOL_DEPLOYER_PRIVATE_KEY and GUILD_PROTOCOL_ADMIN.
///      Optional role addresses default to GUILD_PROTOCOL_ADMIN and should be
///      replaced with dedicated service/governance accounts before production.
contract DeployKokonutGuildProtocol is Script {
    uint256 private constant ANVIL_CHAIN_ID = 31337;
    uint256 private constant GNOSIS_CHAIN_ID = 100;
    uint256 private constant CHIADO_CHAIN_ID = 10200;

    function run()
        external
        returns (
            KokonutGuildRegistry registry,
            KokonutGuildDomain domains,
            KokonutTaskBoard tasks,
            KokonutEvidenceReview reviews,
            KokonutGuildGovernance governance
        )
    {
        require(
            block.chainid == ANVIL_CHAIN_ID || block.chainid == GNOSIS_CHAIN_ID || block.chainid == CHIADO_CHAIN_ID,
            "Unsupported Guild protocol network"
        );
        uint256 deployerKey = vm.envUint("GUILD_PROTOCOL_DEPLOYER_PRIVATE_KEY");
        address admin = vm.envAddress("GUILD_PROTOCOL_ADMIN");
        address reviewer = vm.envOr("GUILD_PROTOCOL_REVIEWER", admin);
        address proposer = vm.envOr("GUILD_PROTOCOL_PROPOSER", admin);
        address objector = vm.envOr("GUILD_PROTOCOL_OBJECTOR", admin);
        address executor = vm.envOr("GUILD_PROTOCOL_EXECUTOR", admin);

        vm.startBroadcast(deployerKey);
        registry = new KokonutGuildRegistry(admin);
        domains = new KokonutGuildDomain(admin, registry);
        tasks = new KokonutTaskBoard(admin, domains);
        reviews = new KokonutEvidenceReview(admin, tasks);
        governance = new KokonutGuildGovernance(admin);

        tasks.setEvidenceReview(address(reviews));
        tasks.grantRole(tasks.TASK_ADMIN_ROLE(), address(governance));
        domains.grantRole(domains.DOMAIN_ADMIN_ROLE(), address(governance));
        reviews.grantRole(reviews.REVIEWER_ROLE(), reviewer);
        governance.grantRole(governance.PROPOSER_ROLE(), proposer);
        governance.grantRole(governance.OBJECTOR_ROLE(), objector);
        governance.grantRole(governance.EXECUTOR_ROLE(), executor);
        governance.setTargetAllowed(address(tasks), true);
        governance.setTargetAllowed(address(domains), true);
        governance.setTargetSelectorAllowed(address(tasks), tasks.cancelTask.selector, true);
        governance.setTargetSelectorAllowed(address(tasks), tasks.markPaid.selector, true);
        governance.setTargetSelectorAllowed(address(domains), domains.setStatus.selector, true);
        governance.setGuildScopedTarget(address(tasks), true);
        governance.setGuildScopedTarget(address(domains), true);
        vm.stopBroadcast();

        console.log("Guild registry:", address(registry));
        console.log("Guild domains:", address(domains));
        console.log("Task board:", address(tasks));
        console.log("Evidence review:", address(reviews));
        console.log("Guild governance:", address(governance));
        console.log("Chain ID:", block.chainid);
        console.log("Admin:", admin);
        console.log("Reviewer:", reviewer);
        console.log("Proposer:", proposer);
        console.log("Objector:", objector);
        console.log("Executor:", executor);
    }
}
