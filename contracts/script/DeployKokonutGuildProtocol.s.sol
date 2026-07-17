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

    struct Config {
        uint256 deployerKey;
        address admin;
        address bootstrap;
        address guildAdmin;
        address domainAdmin;
        address taskAdmin;
        address reviewer;
        address proposer;
        address objector;
        address executor;
    }

    struct Protocol {
        KokonutGuildRegistry registry;
        KokonutGuildDomain domains;
        KokonutTaskBoard tasks;
        KokonutEvidenceReview reviews;
        KokonutGuildGovernance governance;
    }

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
        Config memory config = _readConfig();
        Protocol memory protocol;

        vm.startBroadcast(config.deployerKey);
        protocol.registry = new KokonutGuildRegistry(config.bootstrap);
        protocol.domains = new KokonutGuildDomain(config.bootstrap, protocol.registry);
        protocol.tasks = new KokonutTaskBoard(config.bootstrap, protocol.domains);
        protocol.reviews = new KokonutEvidenceReview(config.bootstrap, protocol.tasks);
        protocol.governance = new KokonutGuildGovernance(config.bootstrap);
        _wire(protocol, config);
        vm.stopBroadcast();

        registry = protocol.registry;
        domains = protocol.domains;
        tasks = protocol.tasks;
        reviews = protocol.reviews;
        governance = protocol.governance;
        _assertHandoff(protocol, config);

        console.log("Guild registry:", address(registry));
        console.log("Guild domains:", address(domains));
        console.log("Task board:", address(tasks));
        console.log("Evidence review:", address(reviews));
        console.log("Guild governance:", address(governance));
        console.log("Chain ID:", block.chainid);
        console.log("Admin:", config.admin);
        console.log("Reviewer:", config.reviewer);
        console.log("Proposer:", config.proposer);
        console.log("Objector:", config.objector);
        console.log("Executor:", config.executor);
    }

    function _readConfig() internal returns (Config memory config) {
        config.deployerKey = vm.envUint("GUILD_PROTOCOL_DEPLOYER_PRIVATE_KEY");
        config.admin = vm.envAddress("GUILD_PROTOCOL_ADMIN");
        config.bootstrap = vm.addr(config.deployerKey);
        config.guildAdmin = vm.envOr("GUILD_PROTOCOL_GUILD_ADMIN", config.admin);
        config.domainAdmin = vm.envOr("GUILD_PROTOCOL_DOMAIN_ADMIN", config.admin);
        config.taskAdmin = vm.envOr("GUILD_PROTOCOL_TASK_ADMIN", config.admin);
        config.reviewer = vm.envOr("GUILD_PROTOCOL_REVIEWER", config.admin);
        config.proposer = vm.envOr("GUILD_PROTOCOL_PROPOSER", config.admin);
        config.objector = vm.envOr("GUILD_PROTOCOL_OBJECTOR", config.admin);
        config.executor = vm.envOr("GUILD_PROTOCOL_EXECUTOR", config.admin);
        require(config.admin != address(0) && config.bootstrap != address(0), "Invalid protocol authority");
    }

    function _wire(Protocol memory p, Config memory c) internal {
        p.tasks.setEvidenceReview(address(p.reviews));
        p.tasks.grantRole(p.tasks.TASK_ADMIN_ROLE(), address(p.governance));
        p.domains.grantRole(p.domains.DOMAIN_ADMIN_ROLE(), address(p.governance));
        p.registry.grantRole(p.registry.DEFAULT_ADMIN_ROLE(), c.admin);
        p.registry.grantRole(p.registry.GUILD_ADMIN_ROLE(), c.guildAdmin);
        p.domains.grantRole(p.domains.DEFAULT_ADMIN_ROLE(), c.admin);
        p.domains.grantRole(p.domains.DOMAIN_ADMIN_ROLE(), c.domainAdmin);
        p.tasks.grantRole(p.tasks.DEFAULT_ADMIN_ROLE(), c.admin);
        p.tasks.grantRole(p.tasks.TASK_ADMIN_ROLE(), c.taskAdmin);
        p.reviews.grantRole(p.reviews.DEFAULT_ADMIN_ROLE(), c.admin);
        p.governance.grantRole(p.governance.DEFAULT_ADMIN_ROLE(), c.admin);
        p.reviews.grantRole(p.reviews.REVIEWER_ROLE(), c.reviewer);
        p.governance.grantRole(p.governance.PROPOSER_ROLE(), c.proposer);
        p.governance.grantRole(p.governance.OBJECTOR_ROLE(), c.objector);
        p.governance.grantRole(p.governance.EXECUTOR_ROLE(), c.executor);
        p.governance.setTargetAllowed(address(p.tasks), true);
        p.governance.setTargetAllowed(address(p.domains), true);
        p.governance.setTargetSelectorAllowed(address(p.tasks), p.tasks.cancelTask.selector, true);
        p.governance.setTargetSelectorAllowed(address(p.tasks), p.tasks.markPaid.selector, true);
        p.governance.setTargetSelectorAllowed(address(p.domains), p.domains.setStatus.selector, true);
        p.governance.setGuildScopedTarget(address(p.tasks), true);
        p.governance.setGuildScopedTarget(address(p.domains), true);

        if (c.bootstrap != c.admin) {
            p.registry.revokeRole(p.registry.GUILD_ADMIN_ROLE(), c.bootstrap);
            p.domains.revokeRole(p.domains.DOMAIN_ADMIN_ROLE(), c.bootstrap);
            p.tasks.revokeRole(p.tasks.TASK_ADMIN_ROLE(), c.bootstrap);
            p.reviews.revokeRole(p.reviews.REVIEWER_ROLE(), c.bootstrap);
            p.governance.revokeRole(p.governance.PROPOSER_ROLE(), c.bootstrap);
            p.governance.revokeRole(p.governance.OBJECTOR_ROLE(), c.bootstrap);
            p.governance.revokeRole(p.governance.EXECUTOR_ROLE(), c.bootstrap);
            p.registry.revokeRole(p.registry.DEFAULT_ADMIN_ROLE(), c.bootstrap);
            p.domains.revokeRole(p.domains.DEFAULT_ADMIN_ROLE(), c.bootstrap);
            p.tasks.revokeRole(p.tasks.DEFAULT_ADMIN_ROLE(), c.bootstrap);
            p.reviews.revokeRole(p.reviews.DEFAULT_ADMIN_ROLE(), c.bootstrap);
            p.governance.revokeRole(p.governance.DEFAULT_ADMIN_ROLE(), c.bootstrap);
        }
    }

    function _assertHandoff(Protocol memory p, Config memory c) internal view {
        require(p.registry.hasRole(p.registry.DEFAULT_ADMIN_ROLE(), c.admin), "Registry admin handoff failed");
        require(p.domains.hasRole(p.domains.DEFAULT_ADMIN_ROLE(), c.admin), "Domain admin handoff failed");
        require(p.tasks.hasRole(p.tasks.DEFAULT_ADMIN_ROLE(), c.admin), "Task admin handoff failed");
        require(p.reviews.hasRole(p.reviews.DEFAULT_ADMIN_ROLE(), c.admin), "Review admin handoff failed");
        require(p.governance.hasRole(p.governance.DEFAULT_ADMIN_ROLE(), c.admin), "Governance admin handoff failed");
        require(p.tasks.evidenceReview() == address(p.reviews), "Evidence review wiring failed");
        require(p.governance.allowedTargets(address(p.tasks)), "Task target not allowlisted");
        require(p.governance.allowedTargets(address(p.domains)), "Domain target not allowlisted");
        if (c.bootstrap != c.admin) {
            require(
                !p.registry.hasRole(p.registry.DEFAULT_ADMIN_ROLE(), c.bootstrap), "Bootstrap registry admin remains"
            );
            require(
                !p.governance.hasRole(p.governance.DEFAULT_ADMIN_ROLE(), c.bootstrap),
                "Bootstrap governance admin remains"
            );
        }
    }
}
