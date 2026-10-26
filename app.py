from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import random
import os
import csv

from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import random
import os
import csv

app = Flask(__name__)
app.secret_key = 'nihongo_secret_key_change_me'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(BASE_DIR, 'vocabulary.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Vocab(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(10), nullable=False)
    kanji = db.Column(db.String(50), nullable=False)
    hiragana = db.Column(db.String(50), nullable=False)
    meaning = db.Column(db.String(100), nullable=False)

def init_database_with_data():
    with app.app_context():
        db.create_all()
        if Vocab.query.count() == 0:
            csv_path = os.path.join(BASE_DIR, 'vocabulary_n3_n4_n5.csv')
            if os.path.exists(csv_path):
                with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        vocab = Vocab(
                            level=row.get('jlpt_level') or row.get('level'),
                            kanji=row.get('word') or row.get('kanji'),
                            hiragana=row.get('reading') or row.get('hiragana'),
                            meaning=row.get('meaning_vi') or row.get('meaning')
                        )
                        db.session.add(vocab)
                    db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/practice/<level>/<mode>', methods=['GET', 'POST'])
def practice(level, mode):
    vocab_list = Vocab.query.filter_by(level=level).all()
    if not vocab_list:
        return "Không tìm thấy từ vựng cho cấp độ này!", 404

    # Khởi tạo hàng đợi ngẫu nhiên
    if 'queue' not in session or session.get('level') != level or session.get('mode') != mode:
        indices = list(range(len(vocab_list)))
        random.shuffle(indices)
        session['queue'] = indices
        session['index'] = 0
        session['score'] = 0
        session['level'] = level
        session['mode'] = mode
        for key in list(session.keys()):
            if key.startswith('quiz_opt_') or key in ['feedback', 'is_correct', 'scored_current']:
                session.pop(key, None)

    queue = session['queue']
    current_index = session['index']

    if current_index >= len(queue):
        score = session.get('score', 0)
        total = len(queue)
        session.pop('queue', None)
        return render_template('result.html', score=score, total=total, level=level)

    vocab_item = vocab_list[queue[current_index]]
    feedback = session.get('feedback')
    is_correct = session.get('is_correct', False)

    quiz_opt_key = f"quiz_opt_{level}_{current_index}"

    if request.method == 'POST':
        user_answer = request.form.get('user_answer', '').strip()
        correct_answer = request.form.get('correct_answer', '').strip()
        action = request.form.get('action')

        if action == 'next':
            session['index'] = current_index + 1
            session.pop('feedback', None)
            session.pop('is_correct', None)
            session.pop('scored_current', None)
            session.modified = True
            return redirect(url_for('practice', level=level, mode=mode))

        # Kiểm tra đáp án
        if user_answer == correct_answer:
            feedback = "Chính xác! 🎉"
            is_correct = True
            if mode == 'quiz' and not session.get('scored_current'):
                session['score'] = session.get('score', 0) + 1
                session['scored_current'] = True
            
            # ĐỐI VỚI MODE INPUT: Gõ đúng xong tự động tăng index luôn, không cần bấm gì cả!
            if mode == 'input':
                session['index'] = current_index + 1
                session.pop('feedback', None)
                session.pop('is_correct', None)
                session.modified = True
                return redirect(url_for('practice', level=level, mode=mode))
        else:
            feedback = "Sai rồi, hãy chọn lại nhé! ❌" if mode == 'quiz' else "Sai rồi, hãy thử lại nhé! ❌"
            is_correct = False

        session['feedback'] = feedback
        session['is_correct'] = is_correct
        session.modified = True
        return redirect(url_for('practice', level=level, mode=mode))

    # Giao diện Luyện gõ (input)
    if mode == 'input':
        return render_template('practice.html', 
                               level=level, 
                               index=current_index + 1, 
                               total=len(queue), 
                               item=vocab_item, 
                               correct_answer=vocab_item.hiragana,
                               feedback=feedback,
                               is_correct=is_correct)
    
    # Giao diện Trắc nghiệm (quiz)
    elif mode == 'quiz':
        if quiz_opt_key not in session:
            correct_val = vocab_item.kanji
            other_vocab = [v.kanji for v in vocab_list if v.kanji != correct_val]
            sample_size = min(2, len(other_vocab))
            wrong_choices = random.sample(other_vocab, sample_size) if sample_size > 0 else ["--", "---"]
            options = wrong_choices + [correct_val]
            random.shuffle(options)
            session[quiz_opt_key] = options
        else:
            options = session[quiz_opt_key]
            if vocab_item.kanji not in options:
                options[0] = vocab_item.kanji
                random.shuffle(options)
                session[quiz_opt_key] = options

        return render_template('quiz.html', 
                               level=level, 
                               index=current_index + 1, 
                               total=len(queue), 
                               item=vocab_item, 
                               options=options, 
                               correct_answer=vocab_item.kanji,
                               feedback=feedback,
                               is_correct=is_correct)

if __name__ == '__main__':
    init_database_with_data()
    app.run(debug=True)