# 호반우 응용 이미지 제작 기록

내장 `image_gen` 도구와 `imagegen` 스킬을 사용했다. OpenAI API/CLI 별도 호출이나 프로젝트 의존성 추가는 없다.

참조: 인수인계 `이미지/호반우_현재/hobanu_body.png`. 각 호출에서 `referenced_image_paths`로 이 파일을 지정하고 `transparent_background: true`를 사용했다.

최종 프로젝트 경로: `tools/hobanu/rain.webp`, `tools/hobanu/sun.webp`, `tools/hobanu/deadline.webp`.
생성된 투명 PNG를 비율을 유지해 축소하고 480×480 투명 캔버스의 같은 기준선에 놓아 WebP로 저장했다. 생성 결과의 색감·세부 선은 공식 원본과 완전히 동일하지 않을 수 있다.

## 공통 프롬프트 (세 호출 모두 동일)

```text
Use case: identity-preserve. Asset: transparent webapp mascot sprite. Reference image is the EXACT Hobanu KNU ox character identity and drawing style to preserve. Same angular rectangular tan ox head, vertical dark brown forehead stripes, two triangular horns, broad side ears, little muzzle, short tan striped legs, black tail, red varsity jacket with white sleeves and small K on chest, thick dark brown clean uniform outlines and flat colors. Keep body proportions and front-facing full-body framing. One character ONLY, square transparent canvas, generous 12% transparent margins, feet baseline at 88% of canvas height. No background, no ground, no shadows, no gradients, no text captions or panel border, no realistic texture. Keep outline fidelity, do not replace by a rounded cute generic cow.
```

## rain — 공통 뒤에 덧붙인 프롬프트

```text
Pose: alert but friendly expression, holds an open small blue umbrella above one side of his head, other hand open showing 2 small raindrops. Show whole umbrella and whole character, no crop.
```

## sun

```text
Pose: smiling, wears small sunglasses pushed up just above the eyes, one hand shading his eyes looking at a small golden sun to the side. Keep distinct ox face and original red jacket. Show whole character.
```

## deadline

```text
Pose: concerned eyebrows, one little sweat drop, holding a clear round cream-colored alarm clock with red case at chest height, other hand points to clock. Friendly urgency, not frightened. Show whole character.
```


## community — 교류 상단 카드 (2026-10-07)

사용자가 고른 수정 투명 PNG를 사용했다. 기존 호반우를 참조해 손을 흔들고 말풍선을 든 모습으로 생성했으며, 코와 이마 형태가 다르다는 피드백을 반영한 결과를 선택했다. 얼굴의 직선 형태, 이마 줄무늬, 코·입 윤곽, 붉은 야구 점퍼를 유지하는 것을 요청했다. 최종 자산은 여백을 정리하고 가로 480px WebP로 저장한 `tools/hobanu/community.webp`다.

## calendar — 캘린더 제목 옆 (2026-10-07)

사용자가 첨부한 양손을 허리에 둔 정면 호반우를 배경 추출 대상으로 지정했다. `image_gen`에 흰 배경을 실제 투명 배경으로 바꾸고, 양손을 내린 자세·이마 줄무늬·지그재그 코·웃는 입·뿔·꼬리·붉은 점퍼를 유지하도록 요청했다. 최종 자산은 세로 240px WebP인 `tools/hobanu/calendar.webp`다.

이 두 자산은 사용자 참조를 바탕으로 만든 프로젝트용 응용 이미지다. 학교가 직접 배포한 원본과 세부 선이나 색이 완전히 동일하지 않을 수 있다. 소스와 `output/app/data/hobanu/`에 같은 파일을 포함한다.
