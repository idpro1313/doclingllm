# region MODULE_CONTRACT [DOMAIN(9): KServe; CONCEPT(9): BinaryProtocol; TECH(9): numpy, json]
## @modulecontract
## @purpose Parse and encode KServe v2 binary infer HTTP bodies compatible with docling KserveV2HttpClient (use_binary_data=True).
## @invariants
## - Supports application/octet-stream with Inference-Header-Content-Length and JSON fallback.
## @changes
## LAST_CHANGE: [v0.2.10 – binary KServe infer request parsing for docling-serve.]
## @modulemap
## FUNC 9[Parse infer HTTP body] => parse_kserve_infer_request
def _module_contract():
    pass
# endregion MODULE_CONTRACT
# GREP_SUMMARY: KServe binary, octet-stream, Inference-Header-Content-Length, tensor decode
# STRUCTURE: ▶ raw bytes → ◇ JSON|binary header → ⊕ tensor payloads → ⎋ infer JSON dict

import json
import logging
from typing import Any, Mapping

import numpy as np

logger = logging.getLogger(__name__)

INFERENCE_HEADER_CONTENT_LENGTH = "Inference-Header-Content-Length"

KSERVE_V2_NUMPY_DATATYPES: dict[str, Any] = {
    "BOOL": np.bool_,
    "UINT8": np.uint8,
    "INT8": np.int8,
    "INT16": np.int16,
    "INT32": np.int32,
    "INT64": np.int64,
    "FP32": np.float32,
    "FP64": np.float64,
    "BYTES": object,
}


# region FUNC__parse_binary_data_size [DOMAIN(6): KServe; CONCEPT(6): BinarySize; TECH(6): dict]
## @purpose Read binary_data_size parameter from KServe tensor metadata.
## @complexity 2
def _parse_binary_data_size(parameters: Mapping[str, Any] | None) -> int | None:
    if not parameters or "binary_data_size" not in parameters:
        return None
    size = parameters["binary_data_size"]
    try:
        parsed_size = int(size)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid binary_data_size value: {size!r}") from exc
    if parsed_size < 0:
        raise ValueError(f"Invalid binary_data_size value: {parsed_size}")
    return parsed_size


# endregion FUNC__parse_binary_data_size


# region FUNC__decode_bytes_tensor [DOMAIN(7): KServe; CONCEPT(7): BYTESDecode; TECH(7): bytes]
## @purpose Decode KServe length-prefixed BYTES wire payload into numpy object array.
## @complexity 5
def _decode_bytes_tensor(raw_payload: bytes, shape: tuple[int, ...]) -> np.ndarray:
    strings: list[Any] = []
    offset = 0
    element_count = int(np.prod(shape)) if shape else len(strings)
    for _ in range(element_count):
        if offset + 4 > len(raw_payload):
            raise ValueError(
                f"Invalid BYTES payload: insufficient bytes for length prefix at offset {offset}"
            )
        string_length = int.from_bytes(raw_payload[offset : offset + 4], byteorder="little")
        offset += 4
        if offset + string_length > len(raw_payload):
            raise ValueError(
                f"Invalid BYTES payload: insufficient bytes for string of length {string_length}"
            )
        strings.append(raw_payload[offset : offset + string_length])
        offset += string_length
    return np.array(strings, dtype=object).reshape(shape)


# endregion FUNC__decode_bytes_tensor


# region FUNC__decode_binary_input_tensor [DOMAIN(8): KServe; CONCEPT(8): TensorDecode; TECH(8): numpy]
## @purpose Decode one binary KServe input tensor payload to numpy array.
## @complexity 4
def _decode_binary_input_tensor(
    raw_payload: bytes,
    datatype: str,
    shape: tuple[int, ...],
) -> np.ndarray:
    np_dtype = KSERVE_V2_NUMPY_DATATYPES.get(datatype)
    if np_dtype is None:
        raise ValueError(f"Unsupported KServe input datatype: {datatype}")
    if datatype == "BYTES":
        return _decode_bytes_tensor(raw_payload, shape)
    array = np.frombuffer(raw_payload, dtype=np_dtype)
    if shape:
        return array.reshape(shape)
    return array


# endregion FUNC__decode_binary_input_tensor


# region FUNC__tensor_to_inline_json_data [DOMAIN(6): KServe; CONCEPT(6): JSONInline; TECH(6): list]
## @purpose Convert decoded numpy tensor to KServe JSON inline data list for downstream handlers.
## @complexity 3
def _tensor_to_inline_json_data(array: np.ndarray, datatype: str) -> list[Any]:
    if datatype == "BYTES":
        values: list[Any] = []
        for value in array.reshape(-1):
            if isinstance(value, bytes):
                try:
                    values.append(value.decode("utf-8"))
                except UnicodeDecodeError:
                    values.append(value.decode("latin-1"))
            else:
                values.append(str(value))
        return values
    return array.reshape(-1).tolist()


# endregion FUNC__tensor_to_inline_json_data


# region FUNC__parse_binary_kserve_request [DOMAIN(9): KServe; CONCEPT(9): BinaryParse; TECH(9): bytes]
## @purpose Parse KServe v2 binary infer request body into JSON-shaped dict with inline tensor data.
## @complexity 7
def _parse_binary_kserve_request(raw_body: bytes, header_len: int) -> dict[str, Any]:
    if header_len < 0 or header_len > len(raw_body):
        raise ValueError(f"Invalid {INFERENCE_HEADER_CONTENT_LENGTH}: {header_len}")

    try:
        header = json.loads(raw_body[:header_len].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid KServe binary request header JSON: {exc}") from exc

    if not isinstance(header, dict):
        raise ValueError("KServe binary request header must be a JSON object")

    binary_payload = raw_body[header_len:]
    offset = 0
    for tensor in header.get("inputs", []):
        if not isinstance(tensor, dict):
            continue
        binary_data_size = _parse_binary_data_size(tensor.get("parameters"))
        if binary_data_size is None:
            continue
        end_offset = offset + binary_data_size
        if end_offset > len(binary_payload):
            raise ValueError(
                f"KServe binary request missing payload for input {tensor.get('name')}: "
                f"expected {binary_data_size} bytes at offset {offset}, got {len(binary_payload) - offset}"
            )
        chunk = binary_payload[offset:end_offset]
        offset = end_offset
        datatype = str(tensor.get("datatype", "")).upper()
        shape = tuple(int(dim) for dim in tensor.get("shape", []))
        array = _decode_binary_input_tensor(chunk, datatype, shape)
        tensor["data"] = _tensor_to_inline_json_data(array, datatype)

    if offset != len(binary_payload):
        logger.warning(
            f"[IMP:6][kserve_binary][TRAILING_BYTES] unconsumed={len(binary_payload) - offset} [WARN]"
        )

    return header


# endregion FUNC__parse_binary_kserve_request


# region FUNC_parse_kserve_infer_request [DOMAIN(9): KServe; CONCEPT(9): HTTPParse; TECH(9): FastAPI]
## @purpose Parse KServe infer POST body from docling (JSON or binary octet-stream).
## @complexity 6
def _header_lookup(headers: Mapping[str, str], name: str) -> str | None:
    if hasattr(headers, "get"):
        value = headers.get(name)
        if value is not None:
            return str(value)
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            return str(value)
    return None


def parse_kserve_infer_request(raw_body: bytes, headers: Mapping[str, str]) -> dict[str, Any]:
    if not raw_body:
        raise ValueError("Empty KServe infer request body")

    header_len_text = _header_lookup(headers, INFERENCE_HEADER_CONTENT_LENGTH)
    content_type = (_header_lookup(headers, "content-type") or "").lower()
    is_octet_stream = "application/octet-stream" in content_type

    if header_len_text is not None:
        try:
            header_len = int(header_len_text)
        except ValueError as exc:
            raise ValueError(
                f"Invalid {INFERENCE_HEADER_CONTENT_LENGTH} header: {header_len_text!r}"
            ) from exc
        parsed = _parse_binary_kserve_request(raw_body, header_len)
        logger.info(
            f"[IMP:7][kserve_binary][PARSED_BINARY] inputs="
            f"{[item.get('name') for item in parsed.get('inputs', [])]} "
            f"header_len={header_len} body_len={len(raw_body)} [IO]"
        )
        return parsed

    if is_octet_stream:
        raise ValueError(
            "Received application/octet-stream without "
            f"{INFERENCE_HEADER_CONTENT_LENGTH}; cannot locate JSON header"
        )

    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(
            "KServe infer request is not UTF-8 JSON; expected binary header "
            f"{INFERENCE_HEADER_CONTENT_LENGTH} for octet-stream payloads "
            f"(body_len={len(raw_body)}, content_type={content_type or 'missing'})"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"KServe infer request is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("KServe infer request JSON must be an object")

    logger.info(
        f"[IMP:7][kserve_binary][PARSED_JSON] inputs="
        f"{[item.get('name') for item in parsed.get('inputs', [])]} [IO]"
    )
    return parsed


# endregion FUNC_parse_kserve_infer_request


# region FUNC_encode_bytes_tensor [DOMAIN(7): KServe; CONCEPT(7): BYTESEncode; TECH(7): bytes]
## @purpose Encode numpy BYTES tensor to KServe length-prefixed wire format (tests and future binary responses).
## @complexity 4
def encode_bytes_tensor(tensor: np.ndarray) -> bytes:
    chunks: list[bytes] = []
    for value in tensor.reshape(-1):
        if isinstance(value, bytes):
            encoded = value
        elif isinstance(value, bytearray | memoryview | np.bytes_):
            encoded = bytes(value)
        elif isinstance(value, str):
            encoded = value.encode("utf-8")
        else:
            encoded = str(value).encode("utf-8")
        chunks.append(len(encoded).to_bytes(4, byteorder="little"))
        chunks.append(encoded)
    return b"".join(chunks)


# endregion FUNC_encode_bytes_tensor


# region FUNC_build_binary_kserve_request [DOMAIN(8): KServe; CONCEPT(8): TestHelper; TECH(8): bytes]
## @purpose Build binary KServe infer request body for tests (mirrors docling KserveV2HttpClient).
## @complexity 5
def build_binary_kserve_request(header: dict[str, Any], raw_input_chunks: list[bytes]) -> tuple[bytes, dict[str, str]]:
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    body = header_bytes + b"".join(raw_input_chunks)
    headers = {
        "Content-Type": "application/octet-stream",
        INFERENCE_HEADER_CONTENT_LENGTH: str(len(header_bytes)),
    }
    return body, headers


# endregion FUNC_build_binary_kserve_request
