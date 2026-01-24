-- 1. FIX PATHS (Ensure Lua looks in the BizHawk root for .dll files)
local root = "C:\\Ironmon\\BizHawk-2.9.1-win-x64\\"
package.path = package.path .. ";" .. root .. "?.lua"
package.cpath = package.cpath .. ";" .. root .. "?.dll"

-- 2. THE "MODULE" FIX
-- We manually load the core C-library instead of calling 'require("socket")' 
-- which triggers the broken socket.lua file.
local socket = require("socket.core") 

-- 3. SETUP SOCKET METHODS (Standard boilerplate to make socket.core act like socket)
local tcp_mt = { __index = socket.tcp() }
function socket.connect(host, port)
    local sock = socket.tcp()
    local res, err = sock:connect(host, port)
    if not res then return nil, err end
    return sock
end

-- Now you can use 'socket' as normal
local host = "127.0.0.1"
local port = 65432
local tcp = assert(socket.connect(host, port))
tcp:settimeout(0)

console.log("Connected to Python Brain!")


function get_player_moves()
    local party_base = 0x02024284 -- Start of Player Party (EWRAM)
    local pv = memory.read_u32_le(party_base + 0)
    local otid = memory.read_u32_le(party_base + 4)
    local magic_word = pv ~ otid 

    local decryption_key = pv % 24
    
    local order_table = {
        {0,1,2,3},{0,1,3,2},{0,2,1,3},{0,2,3,1},{0,3,1,2},{0,3,2,1},
        {1,0,2,3},{1,0,3,2},{1,2,0,3},{1,2,3,0},{1,3,0,2},{1,3,2,0},
        {2,0,1,3},{2,0,3,1},{2,1,0,3},{2,1,3,0},{2,3,0,1},{2,3,1,0},
        {3,0,1,2},{3,0,2,1},{3,1,0,2},{3,1,2,0},{3,2,0,1},{3,2,1,0}
    }
    
    local blocks = order_table[decryption_key + 1]
    local attack_block_offset = -1
    for i, block_num in ipairs(blocks) do
        if block_num == 1 then 
            attack_block_offset = (i - 1) * 12
            break
        end
    end

    local attack_start = party_base + 32 + attack_block_offset

    local moves = {}
    local keys = {
        magic_word & 0xFFFF,         -- Lower 16 bits
        (magic_word >> 16) & 0xFFFF  -- Upper 16 bits
    }

    for i = 0, 3 do
        local raw_move = memory.read_u16_le(attack_start + (i * 2))
        
        -- Use keys[1] for moves 1 & 3, keys[2] for moves 2 & 4
        -- (i % 2) + 1 toggles between index 1 and 2
        local current_key = keys[(i % 2) + 1]
        
        local actual_move = (raw_move ~ current_key) & 0xFFFF
        table.insert(moves, actual_move)
    end
    
    return moves
end

function get_controller_input()
    local pad = joypad.getimmediate()
    local pressed = {}
    
    -- These keys match the 15 keys found by getimmediate()
    local buttons = {"A", "B", "Up", "Down", "Left", "Right", "Start", "Select", "L", "R"}
    
    for _, btn in ipairs(buttons) do
        if pad[btn] then
            table.insert(pressed, btn)
        end
    end
    
    if #pressed == 0 then return "None" end
    return table.concat(pressed, "+")
end

local frameCounter = 0
local throttleLimit = 20 -- Send data to Python every 20 frames
local lastAction = "None"
local prev_state = ""
local frameCounter = 0
local PING_INTERVAL = 10
local last_action = "None"
local move_hold = 40    -- How long to hold the button
local change_delay = 10 -- EXTRA frames to wait if switching directions
local last_direction = "None"

while true do
    frameCounter = frameCounter + 1
    local inBattle = 0
    if memory.readbyte(0x02023BC8) ~= 0 then inBattle = 1 end

    if frameCounter < throttleLimit and inBattle == 1 then
        emu.frameadvance()
    else
        -- 1. READ SENSORS (RAM Addresses for FireRed)
        --local playerX = memory.readbyte(0x03005008)
        local playerX = memory.readbyte(0x02036E4C)
        --local playerY = memory.readbyte(0x0300500A)
        local playerY = memory.readbyte(0x02036E4E)
        local friendHp = memory.readbyte(0x02024282)
        local foeHp = memory.readbyte(0x02024048)
        local menuSelection = memory.readbyte(0x0203AD01)    
        --local mapBank = memory.readbyte(0x03005000)
        --local mapID   = memory.readbyte(0x03005001)
        local mapBank = memory.readbyte(0x02031DBC) -- More stable Bank address
        local mapID   = memory.readbyte(0x02031DBD) -- More stable Map address    
        local dialogActive = 0

        local gameMode = memory.readbyte(0x02023B44)

        local pokemonLvl = memory.readbyte(0x020242D8) --or 0x02023C0E. 2D8 represents the first pokemon's level in party
        local poke2lvl = memory.readbyte(0x0202433C) -- second pokemon level
        --The rest are unverified but based on offsets of prior pokemon levels
        local poke3lvl = memory.readbyte(0x020243A0)
        local poke4lvl = memory.readbyte(0x02024404)
        local poke5lvl = memory.readbyte(0x02024468)
        local poke6lvl = memory.readbyte(0x020244CC)


        local playerHP = memory.read_u16_le(0x020242DA)
        local playerMaxHP = memory.read_u16_le(0x020242DC)

        local enemyHP = memory.read_u16_le(0x02024082)
        local enemyMaxHP = memory.read_u16_le(0x02024084)
        local enemy2HP = memory.read_u16_le(0x20240E6)
        local enemy2MaxHP = memory.read_u16_le(0x20240E8)
        local enemy3HP = memory.read_u16_le(0x202414A)
        local enemy3MaxHP = memory.read_u16_le(0x202414C)
        local enemy4HP = memory.read_u16_le(0x20241AE)
        local enemy4MaxHP = memory.read_u16_le(0x20241B0)
        local enemy5HP = memory.read_u16_le(0x2024212)
        local enemy5MaxHP = memory.read_u16_le(0x2024214)
        local enemy6HP = memory.read_u16_le(0x2024276)
        local enemy6MaxHP = memory.read_u16_le(0x2024278)

        -- Determine battle type
        local battleType = memory.readbyte(0x02022B4C)

        -- bridge.lua updates
        local battleMenu = memory.readbyte(0x02023E82) -- 0: Main Menu, 1: Move Selection
        local cursorSlot = memory.readbyte(0x02023FFC) -- 0 to 3

        local inMenu = memory.readbyte(0x02001D02) -- 0: Overworld, 8: In Menu
        local needsClick = memory.readbyte(0x0202004F)

        if memory.readbyte(0x0203960C) > 0 then inBattle = 1 end
        if memory.readbyte(0x030008F0) == 1 then dialogActive = 1 end       

        local moves = get_player_moves()
        local move_str = table.concat(moves, "|")

        local move1PP = memory.readbyte(0x02023C08)
        local move2PP = memory.readbyte(0x02023C09)
        local move3PP = memory.readbyte(0x02023C0A)
        local move4PP = memory.readbyte(0x02023C0B)

        local e_type1 = memory.readbyte(0x02023C5D)
        local e_type2 = memory.readbyte(0x02023C5E)

        local currentInput = get_controller_input()

        -- 1. Get the dynamic base address from the pointer
        local saveBlockBase = memory.read_u32_le(0x03005008)

        -- 2. Add your offset (FE4)
        local finalAddress = saveBlockBase + 0xFE4

        local gMapHeader = 0x02036DFC
        local mapLocationAddress = gMapHeader + 0x12

        -- 3. Read the badge data from that location
        local badgeData = memory.readbyte(finalAddress)
        local mapLocationId = memory.readbyte(mapLocationAddress)

        local partyFirstPokemonID = memory.readbyte(0x02024284)
        local userActivePokemon = memory.readbyte(0x02023BE4)

        -- 2. SEND STATE TO PYTHON
        local state = string.format("frameCounter:%d,X:%d,Y:%d,InBattle:%d,Dialogue:%d,mapBank:%d,mapID:%d,currHP:%d,maxHP:%d,enemyHP:%d,enemyMaxHP:%d,enemy2HP:%d,enemy2MaxHP:%d,enemy3HP:%d,enemy3MaxHP:%d,enemy4HP:%d,enemy4MaxHP:%d,enemy5HP:%d,enemy5MaxHP:%d,enemy6HP:%d,enemy6MaxHP:%d,battleMenu:%d,cursorSlot:%d,battleType:%d,inMenu:%d,needsClick:%d,partyFirstPokemonID:%d,userActivePokemon:%d,moves:%s,move1PP:%d,move2PP:%d,move3PP:%d,move4PP:%d,e_type1:%d,e_type2:%d,pokemonLvl:%s,poke2lvl:%s,poke3lvl:%s,poke4lvl:%s,poke5lvl:%s,poke6lvl:%s,badgeData:%d,currentInput:%s,mapLocationId:%d,last_direction:%s", 
        frameCounter, playerX, playerY, inBattle, dialogActive, mapBank, mapID, playerHP, playerMaxHP, enemyHP, enemyMaxHP, enemy2HP, enemy2MaxHP, enemy3HP, enemy3MaxHP, enemy4HP, enemy4MaxHP, enemy5HP, enemy5MaxHP, enemy6HP, enemy6MaxHP,
        battleMenu, cursorSlot, battleType, inMenu, needsClick,
        partyFirstPokemonID,
        userActivePokemon,
        move_str,
        move1PP,
        move2PP,
        move3PP,
        move4PP,
        e_type1,
        e_type2,
        pokemonLvl,
        poke2lvl,
        poke3lvl,
        poke4lvl,
        poke5lvl,
        poke6lvl,
        badgeData,
        currentInput,
        mapLocationId,
        last_direction)
        
        -- ignore changes in frameCounter when comparing state
        local state_noframe = state:gsub("frameCounter:%d+,", "")
        local prev_state_noframe = prev_state:gsub("frameCounter:%d+,", "")
        
        if  frameCounter % PING_INTERVAL == 0 then --(state_noframe ~= prev_state_noframe) then --and currentInput ~= "None"
            tcp:send(state .. "\n")
            prev_state = state
            
            if frameCounter >= 3000 then
            frameCounter = 0
            else
                frameCounter = frameCounter + 1
            end
            
            -- 3. RECEIVE COMMAND
            tcp:settimeout(0.5) -- 500 ms timeout
            local response, err = tcp:receive()
            if response then
                local clean_command = response:gsub("%s+", "")
                if clean_command ~= "None" then

                    local hold_frames = 16 -- Default for movement
                    if clean_command == "A" or clean_command == "B" or clean_command == "Start" then
                        hold_frames = 4 -- Just a quick tap for menus/dialogue
                    end

                    if clean_command == "Up" or clean_command == "Down" or clean_command == "Left" or clean_command == "Right" then
                        last_direction = clean_command
                    end

                    -- 1. Press the button
                    joypad.set({ [clean_command] = true })
                    for i = 1, move_hold do
                        emu.frameadvance()
                    end

                    -- 3. Release the button
                    joypad.set({ [clean_command] = false })
                    -- 4. Force a "Release" frame so the game sees the button is up
                    for i = 1, 2 do -- 2 frames of "neutral" helps the game buffer the next input
                        emu.frameadvance()
                    end

                    -- 4. If we changed direction, wait for the "Turning Animation" to finish
                    if clean_command ~= last_action then
                        for i = 1, change_delay do
                            emu.frameadvance()
                        end
                    end
                    last_action = clean_command
                else
                    -- If the AI says "None", just wait 5 frames
                    for i = 1, PING_INTERVAL do
                        emu.frameadvance()
                    end
                    last_action = "None"
                end
            else
                --console.log("Waiting for brain... Error: " .. tostring(err))
                for i = 1, 5 do
                    emu.frameadvance()
                    last_action = "None"
                end -- Don't freeze the emulator if Python crashes
            end
        else 
            for i = 1, 5 do
                emu.frameadvance()
                last_action = "None"
            end --advance frame if the state is the exact same as before
        end
    end
end