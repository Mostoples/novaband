// Nova-Band — read-only view over the packed asset image (tools/fw_assets.py).
// On the board the image lives in the "assets" flash partition and is
// memory-mapped, so nothing is copied: sprites and splash frames are read
// straight from flash through the cache.
#pragma once
#include <stdint.h>
#include <string.h>

#include "asset_ids.h"
#include "gfx.h"

struct AssetEntry {
  char name[24];
  uint32_t type, offset;
  uint16_t w, h, frames, pad;
  uint32_t size, extra;
};
static_assert(sizeof(AssetEntry) == 48, "entry layout must match fw_assets.py");
static_assert(sizeof(gfx::Glyph) == 16, "glyph layout must match fw_assets.py");

class Assets {
 public:
  bool load(const uint8_t* blob) {
    if (!blob || memcmp(blob, "NBA1", 4) != 0) return false;
    base_ = blob;
    count_ = *(const uint32_t*)(blob + 4);
    table_ = (const AssetEntry*)(blob + 16);
    return count_ == (uint32_t)A::COUNT;       // image and firmware must be from the same build
  }
  // Copy everything from entry `from` onward (all but the splash) into RAM
  // (PSRAM on the board). Flash reads go through the same cache as PSRAM and
  // were the bottleneck when sprites and fonts were read from flash per frame.
  bool relocate(int from, void* (*alloc)(size_t)) {
    uint32_t off = table_[from].offset, end = *(const uint32_t*)(base_ + 8);
    uint8_t* m = (uint8_t*)alloc(end - off);
    if (!m) return false;
    memcpy(m, base_ + off, end - off);
    reloc_ = m; relocOff_ = off;
    return true;
  }
  const AssetEntry& e(int id) const { return table_[id]; }
  int frames(int id) const { return table_[id].frames; }

  gfx::Image image(int id, int frame = 0) const {
    const AssetEntry& a = table_[id];
    return {a.w, a.h, (const uint16_t*)(at(a.offset) + (size_t)frame * a.w * a.h * 2)};
  }
  gfx::Sprite sprite(int id, int frame = 0) const {
    const AssetEntry& a = table_[id];
    const uint8_t* p = at(a.offset) + (size_t)frame * a.w * a.h * 3;
    return {a.w, a.h, (const uint16_t*)p, p + (size_t)a.w * a.h * 2};
  }
  gfx::Font font(int id) const {
    const uint8_t* p = at(table_[id].offset);
    const uint16_t* h = (const uint16_t*)p;
    gfx::Font f;
    f.first = h[0]; f.count = h[1]; f.line = h[2]; f.ascent = h[3];
    f.glyphs = (const gfx::Glyph*)(p + 8);
    f.alpha = p + 8 + f.count * sizeof(gfx::Glyph);
    return f;
  }
  const uint8_t* bytes(int id) const { return at(table_[id].offset); }

 private:
  const uint8_t* at(uint32_t off) const { return reloc_ && off >= relocOff_ ? reloc_ + (off - relocOff_) : base_ + off; }
  const uint8_t* base_ = nullptr;
  const uint8_t* reloc_ = nullptr;
  uint32_t relocOff_ = 0;
  const AssetEntry* table_ = nullptr;
  uint32_t count_ = 0;
};
