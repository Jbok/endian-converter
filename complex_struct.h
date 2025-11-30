#ifndef COMPLEX_STRUCT_H
#define COMPLEX_STRUCT_H

#include <stdint.h>
#include "config.h"
#include "external_struct.h"

#define MAX_20   20

typedef struct {  // 탭 인덴테이션, // 주석 스타일
	uint8_t port[10];  // 포트 번호
	uint16_t protocol[10];  // 프로토콜 타입
	uint32_t ip_address[MAX_20];  // IP 주소
} PACKED_STRUCT s1_type;

typedef struct {  // 탭 인덴테이션, // 주석 스타일
	uint8_t port[10];  // 포트 번호


	uint16_t protocol[MAX_20];  // 프로토콜 타입
	s1_type nested_address[2];  // 중첩된 주소 구조체
} PACKED_STRUCT s2_type;

typedef struct {  // 탭 인덴테이션, // 주석 스타일
	s2_type s2[5];  // s2 구조체 배열
	s1_type s1;
} PACKED_STRUCT s3_type;

typedef struct {  // 탭 인덴테이션, // 주석 스타일
	s1_type s1;  // s1 구조체
	s2_type s2;  // s2 구조체
	s3_type s3;  // s3 구조체
	int arr[MAS121][10];
} PACKED_STRUCT s_type;

