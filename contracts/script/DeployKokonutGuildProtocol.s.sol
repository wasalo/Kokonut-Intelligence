// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {Script, console} from "forge-std/Script.sol";
import {KokonutEvidenceReview} from "../src/KokonutEvidenceReview.sol";
import {KokonutGuildDomain} from "../src/KokonutGuildDomain.sol";
import {KokonutGuildGovernance} from "../src/KokonutGuildGovernance.sol";
import {KokonutGuildRegistry} from "../src/KokonutGuildRegistry.sol";
import {KokonutTaskBoard} from "../src/KokonutTaskBoard.sol";

/// @title DeployKokonutGuildProtocol
/// @notice Deploys and wires the operational Guild protocol contracts.
/// @dev Required: GUILD_PROTOCOL_BOOTSTRAP and GUILD_PROTOCOL_ADMIN.
///      Optional role addresses default to GUILD_PROTOCOL_ADMIN and should be
///      replaced with dedicated service/governance accounts before production.
contract DeployKokonutGuildProtocol is Script {
    uint256 private constant ANVIL_CHAIN_ID = 31337;
    uint256 private constant GNOSIS_CHAIN_ID = 100;
    uint256 private constant CHIADO_CHAIN_ID = 10200;

    struct Config {
        address admin;
        address bootstrap;
        address roleAdmin;
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

        vm.startBroadcast();
        (, address broadcaster,) = vm.readCallers();
        require(broadcaster == config.bootstrap, "Bootstrap does not match broadcast sender");
        protocol.registry = new KokonutGuildRegistry(config.bootstrap, config.bootstrap);
        protocol.domains = new KokonutGuildDomain(config.bootstrap, config.bootstrap, protocol.registry);
        protocol.tasks = new KokonutTaskBoard(config.bootstrap, config.bootstrap, protocol.domains);
        protocol.reviews = new KokonutEvidenceReview(config.bootstrap, config.bootstrap, protocol.tasks);
        protocol.governance = new KokonutGuildGovernance(config.bootstrap, config.bootstrap);
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

    function _readConfig() internal view returns (Config memory config) {
        config.admin = vm.envAddress("GUILD_PROTOCOL_ADMIN");
        config.bootstrap = vm.envAddress("GUILD_PROTOCOL_BOOTSTRAP");
        if (block.chainid == ANVIL_CHAIN_ID) {
            config.roleAdmin = vm.envOr("GUILD_PROTOCOL_ROLE_ADMIN", config.admin);
            config.guildAdmin = vm.envOr("GUILD_PROTOCOL_GUILD_ADMIN", config.admin);
            config.domainAdmin = vm.envOr("GUILD_PROTOCOL_DOMAIN_ADMIN", config.admin);
            config.taskAdmin = vm.envOr("GUILD_PROTOCOL_TASK_ADMIN", config.admin);
            config.reviewer = vm.envOr("GUILD_PROTOCOL_REVIEWER", config.admin);
            config.proposer = vm.envOr("GUILD_PROTOCOL_PROPOSER", config.admin);
            config.objector = vm.envOr("GUILD_PROTOCOL_OBJECTOR", config.admin);
            config.executor = vm.envOr("GUILD_PROTOCOL_EXECUTOR", config.admin);
        } else {
            config.roleAdmin = vm.envAddress("GUILD_PROTOCOL_ROLE_ADMIN");
            config.guildAdmin = vm.envAddress("GUILD_PROTOCOL_GUILD_ADMIN");
            config.domainAdmin = vm.envAddress("GUILD_PROTOCOL_DOMAIN_ADMIN");
            config.taskAdmin = vm.envAddress("GUILD_PROTOCOL_TASK_ADMIN");
            config.reviewer = vm.envAddress("GUILD_PROTOCOL_REVIEWER");
            config.proposer = vm.envAddress("GUILD_PROTOCOL_PROPOSER");
            config.objector = vm.envAddress("GUILD_PROTOCOL_OBJECTOR");
            config.executor = vm.envAddress("GUILD_PROTOCOL_EXECUTOR");
        }
        require(
            config.admin != address(0) && config.bootstrap != address(0) && config.roleAdmin != address(0)
                && config.bootstrap != config.admin,
            "Invalid protocol authority"
        );
        require(
            config.guildAdmin != address(0) && config.domainAdmin != address(0) && config.taskAdmin != address(0)
                && config.reviewer != address(0) && config.proposer != address(0) && config.objector != address(0)
                && config.executor != address(0),
            "Invalid operational role"
        );
        if (block.chainid != ANVIL_CHAIN_ID) {
            require(
                config.admin != config.guildAdmin && config.admin != config.domainAdmin
                    && config.admin != config.taskAdmin && config.admin != config.reviewer
                    && config.admin != config.proposer && config.admin != config.objector
                    && config.admin != config.executor && config.admin != config.roleAdmin,
                "Admin must be separate from operational roles"
            );
        }
        require(config.roleAdmin != config.bootstrap, "Role admin must survive bootstrap handoff");
        require(
            config.bootstrap != config.guildAdmin && config.bootstrap != config.domainAdmin
                && config.bootstrap != config.taskAdmin && config.bootstrap != config.reviewer
                && config.bootstrap != config.proposer && config.bootstrap != config.objector
                && config.bootstrap != config.executor,
            "Bootstrap overlaps operational role"
        );
    }

    function _wire(Protocol memory p, Config memory c) internal {
        p.tasks.setEvidenceReview(address(p.reviews));
        p.tasks.grantRole(p.tasks.TASK_ADMIN_ROLE(), address(p.governance));
        p.domains.grantRole(p.domains.DOMAIN_ADMIN_ROLE(), address(p.governance));
        p.registry.grantRole(p.registry.DEFAULT_ADMIN_ROLE(), c.admin);
        p.registry.grantRole(p.registry.ROLE_ADMIN_ROLE(), c.roleAdmin);
        p.registry.grantRole(p.registry.GUILD_ADMIN_ROLE(), c.guildAdmin);
        p.domains.grantRole(p.domains.DEFAULT_ADMIN_ROLE(), c.admin);
        p.domains.grantRole(p.domains.ROLE_ADMIN_ROLE(), c.roleAdmin);
        p.domains.grantRole(p.domains.DOMAIN_ADMIN_ROLE(), c.domainAdmin);
        p.tasks.grantRole(p.tasks.DEFAULT_ADMIN_ROLE(), c.admin);
        p.tasks.grantRole(p.tasks.ROLE_ADMIN_ROLE(), c.roleAdmin);
        p.tasks.grantRole(p.tasks.TASK_ADMIN_ROLE(), c.taskAdmin);
        p.reviews.grantRole(p.reviews.DEFAULT_ADMIN_ROLE(), c.admin);
        p.reviews.grantRole(p.reviews.ROLE_ADMIN_ROLE(), c.roleAdmin);
        p.governance.grantRole(p.governance.DEFAULT_ADMIN_ROLE(), c.admin);
        p.governance.grantRole(p.governance.ROLE_ADMIN_ROLE(), c.roleAdmin);
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
            p.registry.revokeRole(p.registry.ROLE_ADMIN_ROLE(), c.bootstrap);
            p.domains.revokeRole(p.domains.ROLE_ADMIN_ROLE(), c.bootstrap);
            p.tasks.revokeRole(p.tasks.ROLE_ADMIN_ROLE(), c.bootstrap);
            p.reviews.revokeRole(p.reviews.ROLE_ADMIN_ROLE(), c.bootstrap);
            p.governance.revokeRole(p.governance.ROLE_ADMIN_ROLE(), c.bootstrap);
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
            require(!p.registry.hasRole(p.registry.GUILD_ADMIN_ROLE(), c.bootstrap), "Bootstrap guild admin remains");
            require(!p.domains.hasRole(p.domains.DEFAULT_ADMIN_ROLE(), c.bootstrap), "Bootstrap domain admin remains");
            require(!p.domains.hasRole(p.domains.DOMAIN_ADMIN_ROLE(), c.bootstrap), "Bootstrap domain role remains");
            require(!p.tasks.hasRole(p.tasks.DEFAULT_ADMIN_ROLE(), c.bootstrap), "Bootstrap task admin remains");
            require(!p.tasks.hasRole(p.tasks.TASK_ADMIN_ROLE(), c.bootstrap), "Bootstrap task role remains");
            require(!p.reviews.hasRole(p.reviews.DEFAULT_ADMIN_ROLE(), c.bootstrap), "Bootstrap review admin remains");
            require(!p.reviews.hasRole(p.reviews.REVIEWER_ROLE(), c.bootstrap), "Bootstrap reviewer remains");
            require(
                !p.governance.hasRole(p.governance.DEFAULT_ADMIN_ROLE(), c.bootstrap),
                "Bootstrap governance admin remains"
            );
            require(!p.governance.hasRole(p.governance.PROPOSER_ROLE(), c.bootstrap), "Bootstrap proposer remains");
            require(!p.governance.hasRole(p.governance.OBJECTOR_ROLE(), c.bootstrap), "Bootstrap objector remains");
            require(!p.governance.hasRole(p.governance.EXECUTOR_ROLE(), c.bootstrap), "Bootstrap executor remains");
        }
    }
}
