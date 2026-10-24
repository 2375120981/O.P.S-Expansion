local M={}
function M.u32(s,offset)
 assert(type(s)=='string' and offset>=0 and offset%1==0 and offset+4<=#s,'u32 bounds')
 local a,b,c,d=s:byte(offset+1,offset+4)
 return a+256*b+65536*c+16777216*d
end
function M.hex(s)return(s:gsub('.',function(ch)return string.format('%02x',ch:byte())end))end
local function integer(n)
 assert(n>=0 and n<=4294967295 and n%1==0,'u32 range')
 return string.char(n%256,math.floor(n/256)%256,math.floor(n/65536)%256,math.floor(n/16777216)%256)
end
function M.encode(n,kind)
 if kind=='u32' then return integer(n)end
 assert(kind=='f32' and type(n)=='number' and n==n and math.abs(n)<math.huge,'finite float required')
 if n==0 then return integer(0)end
 local sign=n<0 and 2147483648 or 0;n=math.abs(n)
 local mantissa,power=math.frexp(n);local exponent=power-1
 local fraction
 if exponent< -126 then exponent=0;fraction=math.floor(n/2^-149+0.5)
 else
  fraction=math.floor((mantissa*2-1)*8388608+0.5)
  if fraction==8388608 then fraction=0;exponent=exponent+1 end
  exponent=exponent+127
 end
 assert(exponent<255,'float overflow')
 return integer(sign+exponent*8388608+fraction)
end
return M
