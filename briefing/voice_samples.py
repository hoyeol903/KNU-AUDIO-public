"""python -m briefing.voice_samples: generate short real female/male samples."""
from briefing.build import ROOT, read_yaml, audio_info, atomic_bytes
from briefing.qwen_tts import QwenTTS, VOICES


def main():
    config = read_yaml(ROOT/'config/briefing.yaml')
    provider=QwenTTS(device=config.get('tts',{}).get('device','auto'),
                     instructions=config.get('tts',{}).get('instructions',{}))
    text='좋은 아침이에요. 오늘도 즐거운 하루 보내세요.'
    for role, speaker in VOICES.items():
        path=ROOT/'output/qwen-samples'/f'{role}.mp3'
        provider.verify(speaker, role, config['model'])
        print(f'{role} 샘플 생성 시작: {speaker}', flush=True)
        raw=provider.synthesize(text, speaker, config['model'], config['tempo'])
        duration=audio_info(raw)
        atomic_bytes(path, raw)
        print(f'{role}: {path} ({duration}초)', flush=True)


if __name__=='__main__':
    main()
