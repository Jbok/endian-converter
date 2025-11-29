#ifndef COMPLEX_STRUCT_H
#define COMPLEX_STRUCT_H

#include <stdint.h>
#include "config.h"
#include "external_struct.h"

// 내부 구조체: 네트워크 주소 정보 (매크로로 attribute 사용)
typedef struct {  // 탭 인덴테이션, // 주석 스타일
	uint32_t ip_address;  // IP 주소
	uint16_t port;  // 포트 번호
	uint16_t protocol;  // 프로토콜 타입
} PACKED_STRUCT network_address_t;

/* 내부 구조체: 타임스탬프 정보 (직접 attribute 사용) - 2칸 스페이스, 중괄호 다음 줄 */
typedef struct
{
  uint32_t seconds;  /* 초 */
  uint32_t microseconds;  /* 마이크로초 */
  uint16_t timezone;  /* 타임존 오프셋 */
} __attribute__((packed)) timestamp_t;

/**
 * 내부 구조체: 센서 데이터 (매크로로 aligned attribute 사용)
 * 8칸 스페이스 인덴테이션, /** */ 주석 스타일
 */
typedef struct {
        uint32_t sensor_id;       /**< 센서 ID */
        uint16_t temperature;     /**< 온도 값 */
        uint16_t humidity;        /**< 습도 값 */
        uint32_t pressure;        /**< 압력 값 */
        uint16_t status;          /**< 센서 상태 */
} ALIGNED_STRUCT(8) sensor_data_t;

// 내부 구조체: 통계 정보 (직접 attribute 사용 - aligned)
// 4칸 스페이스, // 주석 스타일
typedef struct {
    uint32_t total_count;     // 총 개수
    uint32_t success_count;   // 성공 개수
    uint32_t   error_count;     // 에러 개수
    uint16_t average_latency; // 평균 지연시간
    uint16_t max_latency;     // 최대 지연시간
} __attribute__((aligned(4))) statistics_t;

/* 메인 구조체: 복잡한 데이터 구조 (매크로로 packed attribute 사용) - 탭 인덴테이션 */
typedef struct {
	/* 기본 정보 */
	uint32_t device_id;			/* 디바이스 ID */
	uint32_t firmware_version;		/* 펌웨어 버전 */
	uint16_t device_type;			/* 디바이스 타입 */
	uint16_t status_flags;			/* 상태 플래그 */

	/* 네트워크 정보 (중첩 구조체) */
	network_address_t primary_address;	/* 기본 주소 */
	network_address_t secondary_address;	/* 보조 주소 */

	/* 시간 정보 (중첩 구조체) */
	timestamp_t created_time;		/* 생성 시간 */
	timestamp_t last_updated;		/* 마지막 업데이트 시간 */

	/* 센서 데이터 (중첩 구조체) */
	sensor_data_t    main_sensor;		/* 메인 센서 */
	sensor_data_t    backup_sensor;		/* 백업 센서 */

	/* 통계 정보 (중첩 구조체) */
	statistics_t network_stats;		/* 네트워크 통계 */
	statistics_t sensor_stats;		/* 센서 통계 */

	/* 배열 필드 (Define으로 정의된 크기 사용) */
	uint32_t data_buffer[MAX_DATA_BUFFER_SIZE];		/* 데이터 버퍼 배열 */
	uint16_t sensor_values[MAX_SENSOR_COUNT];		/* 센서 값 배열 */
	network_address_t network_list[MAX_NETWORK_ADDRESSES];	/* 네트워크 주소 배열 */
	uint32_t history_data[MAX_HISTORY_ENTRIES];		/* 히스토리 데이터 배열 */

	/* 외부 헤더 파일의 구조체 변수 */
	device_config_t device_config;		/* 디바이스 설정 (외부 헤더) */
	log_entry_t last_log_entry;		/* 마지막 로그 엔트리 (외부 헤더) */
	memory_info_t memory_info;		/* 메모리 정보 (외부 헤더) */

	/* 추가 데이터 필드 */
	uint16_t checksum;			/* 체크섬 */
	uint16_t sequence_number;		/* 시퀀스 번호 */
	uint32_t total_bytes_sent;		/* 전송된 총 바이트 */
	uint32_t total_bytes_received;		/* 수신된 총 바이트 */
	uint16_t connection_count;		/* 연결 개수 */
	uint16_t error_code;			/* 에러 코드 */
	uint32_t array_count;			/* 배열 개수 */
	uint16_t reserved[2];			/* 예약 필드 */
} PACKED_STRUCT complex_data_t;

#endif /* COMPLEX_STRUCT_H */

