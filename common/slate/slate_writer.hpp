#pragma once
/**
 * Author: Carson Lauer
 * Date: 10 September 2026
 */

#include <cstddef>
#include <cstdint>
#include <cstring>

#include "proto/sats_command.pb.h"

/**
 * Applies ground commands to a slate, by byte offset.
 *
 * The offset comes straight off the wire, so every access is bounds checked
 * and alignment checked before it touches memory; an unchecked offset would
 * be an arbitrary write from anyone who can talk to the radio. Templated on
 * the slate type so the bound is just sizeof(SlateT) and the whole thing is
 * host testable without any pico headers.
 */
template <typename SlateT>
class SlateWriter
{
    // WIDTH_BOOL is one byte on the wire, so the ground and the flight
    // software have to agree that it is one byte here too.
    static_assert(sizeof(bool) == 1, "WIDTH_BOOL assumes a one byte bool");

public:
    explicit SlateWriter(SlateT &slate) : slate_(slate) {}

    /**
     * Apply one command and produce the reply to send back. Writes are
     * answered with the value that actually landed, so the ground can
     * confirm rather than assume.
     */
    SatResponse apply(const SatCmd &cmd)
    {
        switch (cmd.which_cmd) {
        case SatCmd_write_u8_tag:
            return write_uint(cmd.cmd.write_u8.offset, Width_WIDTH_U8,
                              cmd.cmd.write_u8.value);
        case SatCmd_write_u16_tag:
            return write_uint(cmd.cmd.write_u16.offset, Width_WIDTH_U16,
                              cmd.cmd.write_u16.value);
        case SatCmd_write_u32_tag:
            return write_uint(cmd.cmd.write_u32.offset, Width_WIDTH_U32,
                              cmd.cmd.write_u32.value);
        case SatCmd_write_f32_tag:
            return write_f32(cmd.cmd.write_f32.offset, cmd.cmd.write_f32.value);
        case SatCmd_write_bool_tag:
            return write_bool(cmd.cmd.write_bool.offset,
                              cmd.cmd.write_bool.value);
        case SatCmd_read_tag:
            return read_field(cmd.cmd.read.offset, cmd.cmd.read.width);
        default:
            /* No variant set, or one from a newer proto than this build. */
            return reply(Status_STATUS_BAD_COMMAND, 0, Width_WIDTH_UNSPECIFIED);
        }
    }

private:
    SlateT &slate_;

    /* Bytes a field of this width occupies, or 0 if we cannot address it. */
    static std::size_t width_bytes(Width width)
    {
        switch (width) {
        case Width_WIDTH_U8: return 1;
        case Width_WIDTH_U16: return 2;
        case Width_WIDTH_U32: return 4;
        case Width_WIDTH_F32: return 4;
        case Width_WIDTH_BOOL: return sizeof(bool);
        default: return 0;
        }
    }

    /**
     * True if a field of `size` bytes at `offset` lies wholly inside the
     * slate and is naturally aligned.
     *
     * The bound is a subtraction rather than `offset + size <= sizeof`,
     * which wraps around for an offset near the top of a uint32_t and would
     * wave through exactly the writes we are trying to stop. Misaligned
     * accesses are rejected too: they are UB, and they fault outright if
     * UNALIGN_TRP is ever set on the m33.
     */
    static bool addressable(uint32_t offset, std::size_t size)
    {
        if (size == 0 || sizeof(SlateT) < size) {
            return false;
        }
        return offset <= sizeof(SlateT) - size && (offset % size) == 0;
    }

    /* memcpy, not a cast: the field at `offset` may be declared float, and
       storing a uint32_t through a pointer to it breaks strict aliasing.
       Both compile to the same single store. */
    template <typename T>
    void store(uint32_t offset, T value)
    {
        std::memcpy(reinterpret_cast<uint8_t *>(&slate_) + offset, &value,
                    sizeof(T));
    }

    template <typename T>
    T load(uint32_t offset) const
    {
        T value{};
        std::memcpy(&value, reinterpret_cast<const uint8_t *>(&slate_) + offset,
                    sizeof(T));
        return value;
    }

    SatResponse write_uint(uint32_t offset, Width width, uint32_t value)
    {
        const std::size_t size = width_bytes(width);
        if (!addressable(offset, size)) {
            return reply(Status_STATUS_BAD_OFFSET, offset, width);
        }

        switch (width) {
        case Width_WIDTH_U8:
            store<uint8_t>(offset, static_cast<uint8_t>(value));
            break;
        case Width_WIDTH_U16:
            store<uint16_t>(offset, static_cast<uint16_t>(value));
            break;
        default: store<uint32_t>(offset, value); break;
        }

        /* Read it back so the reply carries the truncated value the slate
           actually holds, not the one the ground asked for. */
        return read_field(offset, width);
    }

    /**
     * A bool is stored and loaded through a uint8_t rather than as a bool.
     * Only 0 and 1 are valid representations of a bool, and a neighbouring
     * byte write could leave anything at this offset; memcpy-ing that into
     * a bool would be undefined, so normalise on the way in and compare
     * against zero on the way out.
     */
    SatResponse write_bool(uint32_t offset, bool value)
    {
        if (!addressable(offset, sizeof(bool))) {
            return reply(Status_STATUS_BAD_OFFSET, offset, Width_WIDTH_BOOL);
        }

        store<uint8_t>(offset, value ? 1 : 0);
        return read_field(offset, Width_WIDTH_BOOL);
    }

    SatResponse write_f32(uint32_t offset, float value)
    {
        if (!addressable(offset, sizeof(float))) {
            return reply(Status_STATUS_BAD_OFFSET, offset, Width_WIDTH_F32);
        }

        store<float>(offset, value);
        return read_field(offset, Width_WIDTH_F32);
    }

    SatResponse read_field(uint32_t offset, Width width)
    {
        const std::size_t size = width_bytes(width);
        if (size == 0) {
            /* Nothing to read; the request is not interpretable at all. */
            return reply(Status_STATUS_BAD_COMMAND, offset, width);
        }
        if (!addressable(offset, size)) {
            return reply(Status_STATUS_BAD_OFFSET, offset, width);
        }

        SatResponse rsp = reply(Status_STATUS_OK, offset, width);
        if (width == Width_WIDTH_F32) {
            rsp.which_value = SatResponse_float_value_tag;
            rsp.value.float_value = load<float>(offset);
        } else if (width == Width_WIDTH_BOOL) {
            rsp.which_value = SatResponse_bool_value_tag;
            rsp.value.bool_value = load<uint8_t>(offset) != 0;
        } else {
            rsp.which_value = SatResponse_uint_value_tag;
            rsp.value.uint_value = load_uint(offset, width);
        }
        return rsp;
    }

    uint32_t load_uint(uint32_t offset, Width width) const
    {
        switch (width) {
        case Width_WIDTH_U8: return load<uint8_t>(offset);
        case Width_WIDTH_U16: return load<uint16_t>(offset);
        default: return load<uint32_t>(offset);
        }
    }

    /* Offset and width are echoed on every reply, including the failures,
       so the ground can match a reply to the request that caused it. */
    static SatResponse reply(Status status, uint32_t offset, Width width)
    {
        SatResponse rsp = SatResponse_init_zero;
        rsp.status = status;
        rsp.offset = offset;
        rsp.width = width;
        return rsp;
    }
};
