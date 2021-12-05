--DROP TABLE QUESTIONS;

CREATE TABLE QUESTIONS
(
	Id integer NOT NULL GENERATED ALWAYS AS IDENTITY (INCREMENT 1 START 1),
	Question text NOT NULL UNIQUE,
	Answer integer NOT NULL,
	ChoiceA text NOT NULL,
	ChoiceB text NOT NULL,
	ChoiceC text NOT NULL,
	ChoiceD text NOT NULL,
	Category text,
	Hint text,
	Level integer,
	CONSTRAINT "QUESTIONS_PK" PRIMARY KEY (Id)
);

ALTER TABLE QUESTIONS OWNER to "user";

--DROP TABLE STATISTICS;

CREATE TABLE STATISTICS
(
	Id integer NOT NULL GENERATED ALWAYS AS IDENTITY (INCREMENT 1 START 1),
	Question_Id integer NOT NULL,
	No_Answer integer NOT NULL DEFAULT 0,
	No_ChoiceA integer NOT NULL DEFAULT 0,
	No_ChoiceB integer NOT NULL DEFAULT 0,
	No_ChoiceC integer NOT NULL DEFAULT 0,
	No_ChoiceD integer NOT NULL DEFAULT 0,
	CONSTRAINT "STATISTICS_PK" PRIMARY KEY (Id),
	CONSTRAINT "STATISTICS_QUESTIONS_FK" FOREIGN KEY (Question_Id) REFERENCES QUESTIONS(Id)
		ON UPDATE CASCADE
		ON DELETE CASCADE
);

ALTER TABLE STATISTICS OWNER to "user";

--DROP TABLE LEADERBOARD;
GRANT ALL PRIVILEGES ON DATABASE "quiz_db" TO "user";

CREATE TABLE LEADERBOARD
(
	Id integer NOT NULL GENERATED ALWAYS AS IDENTITY (INCREMENT 1 START 1),
	Username text NOT NULL UNIQUE,
	Score integer NOT NULL,
	No_Games integer NOT NULL,
	Last_Active timestamp,
	CONSTRAINT "LEADERBOARD_PK" PRIMARY KEY (Id)
);

ALTER TABLE LEADERBOARD OWNER to "user";

CREATE OR REPLACE FUNCTION insert_question_statistics() RETURNS TRIGGER AS $$
	BEGIN
		INSERT INTO STATISTICS(Question_Id) SELECT Id FROM QUESTIONS WHERE Question = NEW.Question;
		RETURN NULL;
	END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER questions_on_insert
	AFTER INSERT
	ON QUESTIONS
	FOR EACH ROW
	EXECUTE PROCEDURE insert_question_statistics();