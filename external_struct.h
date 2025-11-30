#ifndef EXTERNAL_STRUCT_H
#define EXTERNAL_STRUCT_H

#include <stdint.h>
#include "config.h"

// 외부 헤더 파일에 정의된 구조체: 디바이스 설정 (직접 attribute 사용)
// 2칸 스페이스 인덴테이션, // 주석 스타일, 중괄호 다음 줄
typedef struct
{
  uint32_t config_id;  // 설정 ID
  uint16_t config_version;  // 설정 버전
  uint32_t flags;  // 설정 플래그
  uint16_t priority;  // 우선순위
} __attribute__((packed)) device_config_t;

/**
 * 외부 헤더 파일에 정의된 구조체: 로그 엔트리 (매크로로 attribute 사용)
 * 4칸 스페이스 인덴테이션, /** */ 주석 스타일
 */
typedef struct {
    uint32_t log_id;           /**< 로그 ID */
    uint32_t      timestamp;        /**< 타임스탬프 */
    uint16_t        log_level;        /**< 로그 레벨 */
    uint8_t reserved;
    uint16_t log_type;         /**< 로그 타입 */
    uint32_t data;             /**< 로그 데이터 */
    char message[100];         /**< 로그 메시지 */
    uint8_t data[100];         /**< 로그 데이터 */
} log_entry_t;

/* 외부 헤더 파일에 정의된 구조체: 메모리 정보 (매크로로 aligned attribute 사용) - 탭 인덴테이션 */
typedef struct {
	uint32_t   total_memory;		/* 총 메모리 */
	uint32_t    used_memory;		/* 사용된 메모리 */
	uint32_t free_memory;		/* 여유 메모리 */
	uint16_t memory_percent;	/* 메모리 사용률 */
} ALIGNED_STRUCT(8) memory_info_t;

#endif /* EXTERNAL_STRUCT_H */

