INSERT INTO platforms (name, display_name, base_url)
VALUES ('ptt', 'PTT', 'https://www.ptt.cc')
ON CONFLICT (name) DO NOTHING;

INSERT INTO boards (platform_id, name, display_name, url)
VALUES
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'facelift', 'facelift', 'https://www.ptt.cc/bbs/facelift/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'BeautySalon', 'BeautySalon', 'https://www.ptt.cc/bbs/BeautySalon/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'MakeUp', 'MakeUp', 'https://www.ptt.cc/bbs/MakeUp/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'Mix_Match', 'Mix_Match', 'https://www.ptt.cc/bbs/Mix_Match/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'fashion', 'fashion', 'https://www.ptt.cc/bbs/fashion/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'Brand', 'Brand', 'https://www.ptt.cc/bbs/Brand/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'e-shopping', 'e-shopping', 'https://www.ptt.cc/bbs/e-shopping/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'NailSalon', 'NailSalon', 'https://www.ptt.cc/bbs/NailSalon/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'Mancare', 'Mancare', 'https://www.ptt.cc/bbs/Mancare/index.html'),
    ((SELECT id FROM platforms WHERE name = 'ptt'), 'teeth_salon', 'teeth_salon', 'https://www.ptt.cc/bbs/teeth_salon/index.html')
ON CONFLICT (platform_id, name) DO NOTHING;
