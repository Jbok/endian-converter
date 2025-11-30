#ifndef CONFIG_H
#define CONFIG_H

/* 배열 크기 정의 */
#define MAX_SENSOR_COUNT       16
#define MAX_NETWORK_ADDRESSES  8


/* Attribute 매크로 정의 */
#ifdef __GNUC__
    #define PACKED_STRUCT       __attribute__((packed))
    #define ALIGNED_STRUCT(n)   __attribute__((aligned(n)))
    #define DEPRECATED_STRUCT   __attribute__((deprecated))
    #define MAY_ALIAS_STRUCT    __attribute__((__may_alias__))
#else
    #define PACKED_STRUCT
    #define ALIGNED_STRUCT(n)
    #define DEPRECATED_STRUCT
    #define MAY_ALIAS_STRUCT
#endif

#endif /* CONFIG_H */

#define MAX_DATA_BUFFER_SIZE   ((32))
#define MAX_HISTORY_ENTRIES    64
#define MAX_DEVICE_NAME_LEN    128