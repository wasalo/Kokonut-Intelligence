// SPDX-License-Identifier: MIT
pragma solidity ^0.8.34;

import {KokonutGuildPoints} from "../src/KokonutGuildPoints.sol";

contract KokonutGuildPointsV2Harness is KokonutGuildPoints {
    function version() external pure returns (uint256) {
        return 2;
    }
}
