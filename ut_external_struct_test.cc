#include <gtest/gtest.h>

extern "C" {
#include "external_struct.h"
}

TEST(DeviceConfigTTest, device_config_t_endian_converter) {
    uint8_t big_endian_raw_device_config_t[] = 
    {
        0xA1, 0xB2, 0xC3, 0xD4, //uint32_t config_id;
        0xA1, 0xB2, //uint16_t config_version;
        0xA1, 0xB2, 0xC3, 0xD4, //uint32_t flags;
        0xA1, 0xB2, //uint16_t priority;
    }

    uint8_t little_endian_raw_device_config_t[] = 
    {
        0xD4, 0xC3, 0xB2, 0xA1, //uint32_t config_id;
        0xB2, 0xA1, //uint16_t config_version;
        0xD4, 0xC3, 0xB2, 0xA1, //uint32_t flags;
        0xB2, 0xA1, //uint16_t priority;
    }

    EXPECT_EQ(sizeof(big_endian_raw_device_config_t), 
sizeof(device_config_t));
    EXPECT_EQ(sizeof(little_endian_raw_device_config_t), 
sizeof(device_config_t));

    messageHdr_type *pBigEndianMsgHdr = (messageHdr_type *)big_endian_raw_device_config_t;
    messageHdr_type *pLittleEndianMsgHdr = (messageHdr_type *)little_endian_raw_device_config_t;
    pBigEndianMsgHdr ->msgType = device_config_t_id;
    pLittleEndianMsgHdr->msgType = ntohs(device_config_t_id);

    Gcci_EndianH2N(big_endian_raw_device_config_t, sizeof(device_config_t));

    EXPECT_EQ(0, memcmp(big_endian_raw_device_config_t, 
little_endian_raw_device_config_t,
sizeof(little_endian_raw_device_config_t)));
}

TEST(LogEntryTTest, log_entry_t_endian_converter) {
    uint8_t big_endian_raw_log_entry_t[] = 
    {
        0xA1, 0xB2, 0xC3, 0xD4, //uint32_t log_id;
        0xA1, 0xB2, 0xC3, 0xD4, //uint32_t timestamp;
        0xA1, 0xB2, //uint16_t log_level;
        0xA1, //uint8_t reserved;
        0xA1, 0xB2, //uint16_t log_type;
        0xA1, 0xB2, 0xC3, 0xD4, //uint32_t data;
    }

    uint8_t little_endian_raw_log_entry_t[] = 
    {
        0xD4, 0xC3, 0xB2, 0xA1, //uint32_t log_id;
        0xD4, 0xC3, 0xB2, 0xA1, //uint32_t timestamp;
        0xB2, 0xA1, //uint16_t log_level;
        0xA1, //uint8_t reserved;
        0xB2, 0xA1, //uint16_t log_type;
        0xD4, 0xC3, 0xB2, 0xA1, //uint32_t data;
    }

    EXPECT_EQ(sizeof(big_endian_raw_log_entry_t), 
sizeof(log_entry_t));
    EXPECT_EQ(sizeof(little_endian_raw_log_entry_t), 
sizeof(log_entry_t));

    messageHdr_type *pBigEndianMsgHdr = (messageHdr_type *)big_endian_raw_log_entry_t;
    messageHdr_type *pLittleEndianMsgHdr = (messageHdr_type *)little_endian_raw_log_entry_t;
    pBigEndianMsgHdr ->msgType = log_entry_t_id;
    pLittleEndianMsgHdr->msgType = ntohs(log_entry_t_id);

    Gcci_EndianH2N(big_endian_raw_log_entry_t, sizeof(log_entry_t));

    EXPECT_EQ(0, memcmp(big_endian_raw_log_entry_t, 
little_endian_raw_log_entry_t,
sizeof(little_endian_raw_log_entry_t)));
}

TEST(MemoryInfoTTest, memory_info_t_endian_converter) {
    uint8_t big_endian_raw_memory_info_t[] = 
    {
        0xA1, 0xB2, 0xC3, 0xD4, //uint32_t total_memory;
        0xA1, 0xB2, 0xC3, 0xD4, //uint32_t used_memory;
        0xA1, 0xB2, 0xC3, 0xD4, //uint32_t free_memory;
        0xA1, 0xB2, //uint16_t memory_percent;
    }

    uint8_t little_endian_raw_memory_info_t[] = 
    {
        0xD4, 0xC3, 0xB2, 0xA1, //uint32_t total_memory;
        0xD4, 0xC3, 0xB2, 0xA1, //uint32_t used_memory;
        0xD4, 0xC3, 0xB2, 0xA1, //uint32_t free_memory;
        0xB2, 0xA1, //uint16_t memory_percent;
    }

    EXPECT_EQ(sizeof(big_endian_raw_memory_info_t), 
sizeof(memory_info_t));
    EXPECT_EQ(sizeof(little_endian_raw_memory_info_t), 
sizeof(memory_info_t));

    messageHdr_type *pBigEndianMsgHdr = (messageHdr_type *)big_endian_raw_memory_info_t;
    messageHdr_type *pLittleEndianMsgHdr = (messageHdr_type *)little_endian_raw_memory_info_t;
    pBigEndianMsgHdr ->msgType = memory_info_t_id;
    pLittleEndianMsgHdr->msgType = ntohs(memory_info_t_id);

    Gcci_EndianH2N(big_endian_raw_memory_info_t, sizeof(memory_info_t));

    EXPECT_EQ(0, memcmp(big_endian_raw_memory_info_t, 
little_endian_raw_memory_info_t,
sizeof(little_endian_raw_memory_info_t)));
}
