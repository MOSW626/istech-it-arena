#!/usr/bin/env python3
"""차량 식별 마커(ArUco) 생성 + 자체 검증.

    pip install opencv-python numpy
    python3 make_vehicle_marker.py 7

`marker_DICT_4X4_50_id7.png`(공유·시뮬용)과 `.svg`(인쇄용)를 만듭니다.
SVG는 물리 치수(mm)로 그려지므로 브라우저에서 그냥 인쇄하면 정확히 5 cm가 나옵니다.

만든 뒤 스스로 다시 검출해 봅니다. 이 검증을 통과하지 못하면 파일을 남기지 않습니다.
"""
import argparse, sys
import cv2, numpy as np

COURSE_DICT = "DICT_4X4_50"      # 코스 ArUco가 쓰는 사전 (track/README.md §3)
COURSE_IDS = {0, 20, 30, 45}     # 코스에 설치된 ID — 차량 마커로 쓸 수 없음
PNG_PX = 1000


def build(dict_name, marker_id, size_mm, quiet_ratio, out_stem):
    if dict_name == COURSE_DICT and marker_id in COURSE_IDS:
        sys.exit(f"[거부] ID {marker_id}는 코스 마커 예약 ID입니다 "
                 f"({COURSE_DICT}의 {sorted(COURSE_IDS)}). 다른 ID를 쓰세요.")

    attr = getattr(cv2.aruco, dict_name, None)
    if attr is None:
        sys.exit(f"[거부] 알 수 없는 사전: {dict_name}")
    d = cv2.aruco.getPredefinedDictionary(attr)
    n_ids, bits = d.bytesList.shape[0], d.markerSize
    if not 0 <= marker_id < n_ids:
        sys.exit(f"[거부] {dict_name}의 ID 범위는 0~{n_ids - 1}입니다.")

    cells = bits + 2                                  # 검은 테두리 포함
    quiet_px = int(round(PNG_PX * quiet_ratio))
    code_px = PNG_PX - 2 * quiet_px
    code_px -= code_px % cells                        # 셀 경계를 정수 픽셀에 맞춤
    quiet_px = (PNG_PX - code_px) // 2

    code = cv2.aruco.generateImageMarker(d, marker_id, code_px)
    png = np.full((PNG_PX, PNG_PX), 255, np.uint8)
    png[quiet_px:quiet_px + code_px, quiet_px:quiet_px + code_px] = code

    verify(png, d, marker_id, cells, quiet_px, code_px)

    code_mm = size_mm * code_px / PNG_PX
    cv2.imwrite(f"{out_stem}.png", png)
    with open(f"{out_stem}.svg", "w") as f:
        f.write(svg(code, cells, size_mm, code_mm))
    return code_mm, code_mm / cells


def verify(png, d, marker_id, cells, quiet_px, code_px):
    """생성 결과를 기본 파라미터로 다시 검출한다. 이슈 #1에서 문제가 된 부분."""
    _, ids, _ = cv2.aruco.ArucoDetector(d, cv2.aruco.DetectorParameters()).detectMarkers(png)
    got = ids.flatten().tolist() if ids is not None else []
    if got != [marker_id]:
        sys.exit(f"[검증 실패] 기본 파라미터 재검출 결과가 {got}입니다 (기대: [{marker_id}]).")

    step = code_px / cells
    impure = sum(
        1
        for i in range(cells)
        for j in range(cells)
        if 1 < (png[quiet_px + int(i * step):quiet_px + int((i + 1) * step),
                    quiet_px + int(j * step):quiet_px + int((j + 1) * step)] > 127).mean() * 100 < 99
    )
    if impure:
        sys.exit(f"[검증 실패] 격자에 정렬되지 않은 셀 {impure}/{cells * cells}개.")
    print(f"  검증 통과 — 기본 파라미터로 id={marker_id} 재검출, 전 {cells * cells}칸 격자 정렬 OK")


def svg(code, cells, size_mm, code_mm):
    """물리 치수(mm)로 그려 100% 배율 인쇄를 보장한다."""
    step = code_mm / cells
    off = (size_mm - code_mm) / 2
    px = code.shape[0] // cells
    white = [
        f'<rect x="{off + j * step:.4f}" y="{off + i * step:.4f}" '
        f'width="{step:.4f}" height="{step:.4f}" fill="#fff"/>'
        for i in range(cells) for j in range(cells)
        if code[int((i + 0.5) * px), int((j + 0.5) * px)] > 127
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size_mm}mm" height="{size_mm}mm" '
        f'viewBox="0 0 {size_mm} {size_mm}">\n'
        f'<rect width="{size_mm}" height="{size_mm}" fill="#fff"/>\n'
        f'<rect x="{off:.4f}" y="{off:.4f}" width="{code_mm:.4f}" height="{code_mm:.4f}" fill="#000"/>\n'
        + "\n".join(white) + "\n</svg>\n"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="차량 식별 마커(ArUco) 생성 + 자체 검증")
    p.add_argument("id", type=int, help="마커 ID (이슈 #1에서 팀 간 중복을 피해 고르세요)")
    p.add_argument("--dict", default=COURSE_DICT, help=f"ArUco 사전 (기본 {COURSE_DICT})")
    p.add_argument("--size-mm", type=float, default=50.0, help="판 전체 한 변, mm (기본 50 = 5cm)")
    p.add_argument("--quiet-ratio", type=float, default=0.15,
                   help="판 대비 사방 흰 여백 비율 (기본 0.15 — 코스 마커와 같은 비율)")
    p.add_argument("--out", help="출력 파일 이름 (확장자 제외)")
    a = p.parse_args()

    stem = a.out or f"marker_{a.dict}_id{a.id}"
    code_mm, cell_mm = build(a.dict, a.id, a.size_mm, a.quiet_ratio, stem)
    print(f"  {stem}.png  — 이슈 공유·시뮬레이션용 ({PNG_PX}x{PNG_PX} px)")
    print(f"  {stem}.svg  — 인쇄용. 브라우저에서 열고 배율 100%로 인쇄하세요")
    print(f"\n  판 전체 {a.size_mm:.0f} mm / 코드 영역 {code_mm:.1f} mm / 셀 {cell_mm:.2f} mm")
    print(f"  이슈 #1에 남기실 내용:  {a.dict} id={a.id}")
