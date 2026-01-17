

-- Run this while looking at an enemy with, for example, 15 HP
local targetHP = 21 -- CHANGE THIS to the enemy's current HP
local startSearch = 0x02024000
local endSearch = 0x02024600

local allowed = {
    [0x2024082]=true,[0x2024084]=true,[0x20240E6]=true,[0x20240E8]=true,
    [0x20240F6]=true,[0x202414A]=true,[0x202414C]=true,[0x20242E0]=true,
}

for addr = startSearch, endSearch, 2 do
    -- if not allowed[addr] then -- Skip addresses not in the allowed list
    --     goto continue
    -- end
    local value = memory.read_u16_le(addr)
    if value >= targetHP - 2 and value <= targetHP + 2 then
        print(string.format("Found potential Enemy HP at: 0x%X. Value: %d", addr, value))
    end
    ::continue::
end