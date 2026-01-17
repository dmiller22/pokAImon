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

local frameCounter = 0
local throttleLimit = 20 -- Send data to Python every 20 frames
local lastAction = "None"
local prev_state = ""

while true do
    frameCounter = frameCounter + 1
    local inBattle = 0
    if memory.readbyte(0x02023BC8) ~= 0 then inBattle = 1 end

    if frameCounter < throttleLimit and inBattle == 1 then
        emu.frameadvance()
    else
        -- 1. READ SENSORS (RAM Addresses for FireRed)
        local playerX = memory.readbyte(0x03005008)
        local playerY = memory.readbyte(0x0300500A)
        local friendHp = memory.readbyte(0x02024282)
        local foeHp = memory.readbyte(0x02024048)
        local menuSelection = memory.readbyte(0x0203AD01)    
        --local mapBank = memory.readbyte(0x03005000)
        --local mapID   = memory.readbyte(0x03005001)
        local mapBank = memory.readbyte(0x02031DBC) -- More stable Bank address
        local mapID   = memory.readbyte(0x02031DBD) -- More stable Map address    
        local dialogActive = 0

        local gameMode = memory.readbyte(0x02023B44)

        local playerHP = memory.read_u16_le(0x020242DA)
        local playerMaxHP = memory.read_u16_le(0x020242DC)

        local enemyHP = memory.read_u16_le(0x02024082)
        local enemyMaxHP = memory.read_u16_le(0x02024084)
        local enemy2HP = memory.read_u16_le(0x20240E6)
        local enemy2MaxHP = memory.read_u16_le(0x20240E8)
        local enemy3HP = memory.read_u16_le(0x202414A)
        local enemy3MaxHP = memory.read_u16_le(0x202414C)
        --Still need locations for party members 4-6.

        -- Determine battle type
        local battleType = memory.readbyte(0x02022B4C)

        -- bridge.lua updates
        local battleMenu = memory.readbyte(0x02023E82) -- 0: Main Menu, 1: Move Selection
        local cursorSlot = memory.readbyte(0x02023FFC) -- 0 to 3

        if memory.readbyte(0x02023BC8) ~= 0 then inBattle = 1 end
        if memory.readbyte(0x030008F0) == 1 then dialogActive = 1 end        

        -- 2. SEND STATE TO PYTHON
        local state = string.format("X:%d,Y:%d,InBattle:%d,Dialogue:%d,mapBank:%d,mapID:%d,currHP:%d,maxHP:%d,enemyHP:%d,enemyMaxHP:%d,battleMenu:%d,cursorSlot:%d,battleType:%d\n", 
        playerX, playerY, inBattle, dialogActive, mapBank, mapID, playerHP, playerMaxHP, enemyHP, enemyMaxHP, battleMenu, cursorSlot, battleType)

        if (state ~= prev_state) then
            tcp:send(state .. "\n")

            -- 3. RECEIVE COMMAND
            local response, err = tcp:receive()
            if response then
                --console.log("Action from Brain: " .. response)
                local clean_command = response:gsub("%s+", "")
                if clean_command ~= "None" then
                    -- 1. Press the button
                    --joypad.set({ [clean_command] = true })
                    -- 2. Hold it for 3 frames (GBA standard for guaranteed registration)
                    for i = 1, 3 do
                        emu.frameadvance()
                    end
                    -- 3. Release the button
                    --joypad.set({ [clean_command] = false })
                    -- 4. Force a "Release" frame so the game sees the button is up
                    emu.frameadvance()
                else
                    -- If the AI says "None", just wait 1 frame
                    emu.frameadvance()
                end
            else
                --console.log("Waiting for brain... Error: " .. tostring(err))
                emu.frameadvance() -- Don't freeze the emulator if Python crashes
            end
        else 
            emu.frameadvance() --advance frame if the state is the exact same as before
        end
    end
end