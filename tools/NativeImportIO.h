// Process-local, bounded observations. No paths, payloads, or identifiers leave C.
#ifndef LAB_IMPORT_IO_H
#define LAB_IMPORT_IO_H
#include <stdint.h>
enum { LAB_IO_AREAS=2, LAB_IO_OPS=19, LAB_IO_LIMIT=100000 };
typedef struct {
 uint32_t calls, failures, last_errno, permission_failures, missing_failures;
} LabIOCell;
typedef struct {
 LabIOCell cells[LAB_IO_AREAS][LAB_IO_OPS];
 uint32_t capped;
} LabIOSnapshot;
void LabImportIOBegin(void);
void LabImportIOEnd(LabIOSnapshot *snapshot);
const char *LabImportIOOperation(unsigned int index);
#endif
