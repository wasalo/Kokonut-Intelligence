// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {KokonutGuildPoints} from "../src/KokonutGuildPoints.sol";

contract KokonutGuildPointsV2Harness is KokonutGuildPoints {
    function version() external pure returns (uint256) {
        return 2;
    }
}
