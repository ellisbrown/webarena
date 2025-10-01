"""base class for evaluation"""
# answer string match
import collections
import html
import importlib
import json
import re
import time
import urllib
from pathlib import Path
from typing import Any, Optional, Tuple, Union
from urllib.parse import urljoin

import evaluate  # type: ignore[import]
import requests
from beartype import beartype
from beartype.door import is_bearable
from nltk.tokenize import word_tokenize  # type: ignore
from PIL import Image
from playwright.sync_api import CDPSession, Page

from ..browser_env import Action, StateInfo, Trajectory
from .image_utils import get_image_ssim
from .helper_functions import (
    PseudoPage,
    get_query_text,
    get_query_text_lowercase,
    gitlab_get_project_memeber_role,
    llm_fuzzy_match,
    llm_ua_match,
    reddit_get_latest_comment_content_by_username,
    reddit_get_latest_comment_obj_by_username,
    reddit_get_parent_comment_username_of_latest_comment_by_username,
    reddit_get_post_url,
    shopping_get_latest_order_url,
    shopping_get_num_reviews,
    shopping_get_order_product_name_list,
    shopping_get_order_product_option,
    shopping_get_order_product_quantity,
    shopping_get_product_attributes,
    shopping_get_product_price,
    shopping_get_rating_as_percentage,
    shopping_get_sku_latest_review_author,
    shopping_get_sku_latest_review_rating,
    shopping_get_sku_latest_review_text,
)


class Evaluator(object):
    def __init__(self, eval_tag: str = "") -> None:
        self.eval_tag = eval_tag

    @beartype
    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage,
        client: CDPSession,
    ) -> float:
        raise NotImplementedError

    @staticmethod
    def get_last_action(trajectory: Trajectory) -> Action:
        try:
            is_bearable(trajectory[-1], Action)
            last_action = trajectory[-1]
        except Exception:
            raise ValueError(
                "The last element of trajectory should be an action, add a fake stop action if needed"
            )

        return last_action  # type: ignore[return-value]

    @staticmethod
    def get_last_state(trajectory: Trajectory) -> StateInfo:
        try:
            is_bearable(trajectory[-2], StateInfo)
            last_state = trajectory[-2]
        except Exception:
            raise ValueError(
                "The second last element of trajectory should be a state, add a fake stop action if needed"
            )

        return last_state  # type: ignore[return-value]

class NumericEvaluator(Evaluator):
    """Check if the numerical relationship is correct"""

    @staticmethod
    def str_2_int(s: str) -> Optional[int]:
        try:
            s = s.strip()
            if "," in s:
                s = s.replace(",", "")

            return int(s)
        except ValueError:
            # Return None if the string cannot be converted to int
            print(f"[NumericEvaluator error]: Cannot convert {s} to int")
            return None

    @staticmethod
    def compare_inequality(
        value: Union[int, float], inequality: str, tol: float = 1e-8
    ) -> bool:
        """
        Compare a value (int or float) against an inequality string.

        Args:
        - value (int/float): The value to be compared.
        - inequality (str): Inequality in the form of "< 700", ">= 300", etc.
        - tol (float): Tolerance for floating point comparisons.

        Returns:
        - bool: True if the value satisfies the inequality, False otherwise.
        """
        # Extract the operator and the number from the inequality string
        ops = {
            "<=": lambda x, y: x <= y + tol,
            ">=": lambda x, y: x >= y - tol,
            "==": lambda x, y: abs(x - y) <= tol,
            "<": lambda x, y: x < y + tol,
            ">": lambda x, y: x > y - tol,
        }

        for op, func in ops.items():
            if op in inequality:
                _, num = inequality.split(op)
                return func(value, float(num.strip()))

        raise ValueError(f"Invalid inequality string: {inequality}")

class StringEvaluator(Evaluator):
    """Check whether the answer is correct with:
    exact match: the answer is exactly the same as the reference answer
    must include: each phrase in the reference answer must be included in the answer
    fuzzy match: the answer is similar to the reference answer, using LLM judge
    """

    def __init__(self, model: str = "gpt-4o") -> None:
        self.model = model
        super().__init__()

    @staticmethod
    @beartype
    def clean_answer(answer: str) -> str:
        answer = answer.strip()
        if answer.startswith("'") and answer.endswith("'"):
            answer = answer[1:-1]
        elif answer.startswith('"') and answer.endswith('"'):
            answer = answer[1:-1]
        return answer.lower()

    @staticmethod
    @beartype
    def exact_match(ref: str, pred: Union[str, int]) -> float:
        if isinstance(pred, int):
            pred = str(pred)
        return float(
            StringEvaluator.clean_answer(pred)
            == StringEvaluator.clean_answer(ref)
        )

    @staticmethod
    @beartype
    def must_include(ref: str, pred: str, tokenize: bool = False) -> float:
        clean_ref = StringEvaluator.clean_answer(ref)
        clean_pred = StringEvaluator.clean_answer(pred)
        # tokenize the answer if the ref is a single word
        # prevent false positive (e.g, 0)
        if (
            tokenize
            and len(clean_ref) == 1
            and len(word_tokenize(clean_ref)) == 1
        ):
            tok_pred = word_tokenize(clean_pred)
            return float(clean_ref in tok_pred)
        else:
            return float(clean_ref in clean_pred)

    @staticmethod
    @beartype
    def must_exclude(ref: str, pred: str) -> float:
        """Returns 1 if pred is not in ref, and 0 otherwise"""
        clean_ref = StringEvaluator.clean_answer(ref)
        clean_pred = StringEvaluator.clean_answer(pred)
        # tokenize the answer if the ref is a single word
        # prevent false positive (e.g, 0)
        if len(word_tokenize(clean_ref)) == 1:
            tok_pred = word_tokenize(clean_pred)
            return float(clean_ref not in tok_pred)
        else:
            return float(clean_ref not in clean_pred)

    @staticmethod
    @beartype
    def fuzzy_match(ref: str, pred: str, intent: str, model: str = "gpt-4o") -> float:
        return llm_fuzzy_match(pred, ref, intent, model)

    @staticmethod
    @beartype
    def ua_match(ref: str, pred: str, intent: str, model: str = "gpt-4o") -> float:
        return llm_ua_match(pred, ref, intent, model)

    @beartype
    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage | None = None,
        client: CDPSession | None = None,
    ) -> float:
        with open(config_file, "r") as f:
            configs = json.load(f)

        last_action = self.get_last_action(trajectory)
        pred = self.clean_answer(last_action["answer"])

        score = 1.0
        for approach, value in configs["eval"]["reference_answers"].items():
            match approach:
                case "exact_match":
                    score *= self.exact_match(ref=value, pred=pred)
                case "required_values":
                    required_values = value
                    assert isinstance(required_values, list)
                    pred = NumericEvaluator.str_2_int(pred)
                    if pred is None:
                        score = 0.0
                    else:
                        for v in required_values:
                            value_or = v.split(" |OR| ")
                            score *= any(
                                [
                                    NumericEvaluator.compare_inequality(
                                        pred, value
                                    )
                                    for value in value_or
                                ]
                            )
                case "must_include":
                    assert isinstance(value, list)
                    for must_value in value:
                        value_or = must_value.split(" |OR| ")
                        score *= any([self.must_include(ref=v, pred=pred, tokenize=(len(value) == 1)) for v in value_or])
                case "must_exclude":
                    assert isinstance(value, list)
                    for must_excl_value in value:
                        score *= self.must_exclude(
                            ref=must_excl_value, pred=pred
                        )
                case "one_of":
                    assert isinstance(value, list)
                    found = False
                    for one_of_value in value:
                        one_of_value = self.clean_answer(one_of_value)
                        if one_of_value in pred:
                            found = True
                            break
                    score = score * found
                case "fuzzy_match":
                    intent = configs["intent"]
                    if value == "N/A":
                        # if the instruction only asks the model to generate N/A when encountering an unachievable task
                        # without more concrete reasons
                        score *= self.exact_match(ref=value, pred=pred)
                        # if the instruction also asks the model to generate the reason why the task is unachievable
                        # this should be the default as it will prevent false positive N/A`
                        if score != 1:
                            score = 1.0 * self.ua_match(
                                intent=configs["intent"],
                                ref=configs["eval"]["string_note"],
                                pred=pred,
                                model=self.model,
                            )
                    else:
                        if isinstance(value, str):
                            value = [value]
                        assert isinstance(value, list)
                        for reference in value:
                            score *= self.fuzzy_match(
                                ref=reference,
                                pred=pred,
                                intent=intent,
                                model=self.model,
                            )
                        # convert to 0/1 float. if any listed reference incorrect, the score is 0
                        # only marked as correct if all listed references are at least partially correct
                        score = float(score > 0)
        return score

class StringSoftEvaluator(Evaluator):
    """Use text generation metrics such as BLEU, ROUGE, etc. to evaluate the answer"""

    @beartype
    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage | None = None
    ) -> float:
        with open(config_file, "r") as f:
            configs = json.load(f)

        last_action = self.get_last_action(trajectory)
        pred = last_action["answer"]
        ref = configs["eval"]["reference_answers"]
        # rouge
        m = evaluate.load("rouge")
        # rouge = m.compute(predictions=[pred], references=[ref])
        # return float(rouge["rouge1"])
        raise NotImplementedError("Not implemented yet")

class URLExactEvaluator(Evaluator):
    """Check whether the URL is exactly the same as of the reference URLs"""

    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage,
        client: CDPSession | None = None,
    ) -> float:
        with open(config_file, "r") as f:
            configs = json.load(f)

        def clean_url(url: str) -> str:
            url = str(url)
            # Replace http://localhost with http://127.0.0.1 to keep things consistent across evals.
            url = url.replace("localhost", "127.0.0.1")
            if url.endswith("/"):
                url = url[:-1]
            return url

        def parse_url(url: str) -> tuple[str, dict[str, list[str]]]:
            """Parse a URL into its base, path, and query components."""
            parsed_url = urllib.parse.urlparse(url)
            base_path = parsed_url.netloc + parsed_url.path
            query = urllib.parse.parse_qs(parsed_url.query)
            return base_path, query

        def parse_urls(
            urls: list[str],
        ) -> tuple[list[str], dict[str, set[str]]]:
            """Parse a list of URLs."""
            base_paths = []
            queries = collections.defaultdict(set)
            for url in urls:
                base_path, query = parse_url(url)
                base_paths.append(base_path)
                for k, v in query.items():
                    queries[k].update(v)
            return base_paths, queries

        pred = clean_url(page.url)
        ref_urls = configs["eval"]["reference_url"].split(" |OR| ")
        ref_urls = [clean_url(url) for url in ref_urls]
        matching_rule = configs["eval"].get("url_note", "EXACT")
        if matching_rule == "EXACT":
            if pred in ref_urls:
                return 1.0
            else:
                return 0.0
        elif matching_rule == "GOLD in PRED":
            ref_base_paths, ref_queries = parse_urls(ref_urls)
            pred_base_paths, pred_query = parse_url(pred)

            base_score = float(
                any(
                    [
                        ref_base_path in pred_base_paths
                        for ref_base_path in ref_base_paths
                    ]
                )
            )
            query_score = 1.0
            for k, possible_values in ref_queries.items():
                query_score *= float(
                    any(
                        possible_ref_value in pred_query.get(k, [])
                        for possible_ref_value in possible_values
                    )
                )
            score = base_score * query_score

        else:
            raise ValueError(f"Unknown matching rule: {matching_rule}")

        return score

class HTMLContentExactEvaluator(Evaluator):
    """Check whether the contents appear in the page"""

    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage,
        client: CDPSession | None = None,
    ) -> float:
        with open(config_file, "r") as f:
            configs = json.load(f)

        targets = configs["eval"]["program_html"]

        score = 1.0
        for target in targets:
            target_url: str = target["url"]  # which url to check
            if target_url.startswith("func"):
                func = target_url.split("func:")[1]
                func = func.replace("__last_url__", page.url)
                target_url = eval(func)

            locator: str = target["locator"]  # js element locator

            # navigate to that url
            prev_page = None
            if target_url != "last":
                prev_page = page
                page = page.context.new_page()
                page.goto(target_url)
                time.sleep(3)  # TODO [shuyanzh]: fix this hard-coded sleep

            # empty, use the full page
            if not locator.strip():
                selected_element = page.content()
            # use JS to select the element
            elif locator.startswith("document.") or locator.startswith(
                "[...document."
            ):
                if "prep_actions" in target:
                    try:
                        for prep_action in target["prep_actions"]:
                            page.evaluate(f"() => {prep_action}")
                    except Exception:
                        pass
                try:
                    selected_element = str(page.evaluate(f"() => {locator}"))
                    if not selected_element:
                        selected_element = ""
                except Exception:
                    # the page is wrong, return empty
                    selected_element = ""
            elif locator.startswith("lambda:"):
                try:
                    locator = locator.lstrip("lambda:")
                    selected_element = page.evaluate(locator)
                    if not selected_element:
                        selected_element = None
                except Exception:
                    # the page is wrong, return empty
                    selected_element = None
            # run program to call API
            elif locator.startswith("func:"):  # a helper function
                func = locator.split("func:")[1]
                func = func.replace("__page__", "page")
                selected_element = eval(func)
            else:
                raise ValueError(f"Unknown locator: {locator}")

            # If the selected element is None, then the page is wrong
            if selected_element is None:
                score = 0.0
                break

            selected_element = html.unescape(selected_element)

            if "exact_match" in target["required_contents"]:
                required_contents = target["required_contents"]["exact_match"]
                cur_score = StringEvaluator.exact_match(
                    ref=required_contents, pred=selected_element
                )
                score *= float(cur_score)
                # print(f"[exact match] {cur_score}, selected element: {selected_element}, required contents: {required_contents}")
            elif "must_include" in target["required_contents"]:
                required_contents = target["required_contents"]["must_include"]
                assert isinstance(required_contents, list)
                for content in required_contents:
                    content_or = content.split(" |OR| ")
                    cur_score = any(
                        [
                            StringEvaluator.must_include(
                                ref=content,
                                pred=selected_element,
                                tokenize=False,
                            )
                            for content in content_or
                        ]
                    )
                    score *= float(cur_score)
                    # print(f"[must include] {cur_score}, selected element: {selected_element}, required contents: {content_or}")
            elif "must_exclude" in target["required_contents"]:
                required_contents = target["required_contents"]["must_exclude"]
                assert isinstance(required_contents, list)
                for content in required_contents:
                    assert " |OR| " not in content
                    cur_score = StringEvaluator.must_exclude(
                        content, pred=selected_element
                    )
                    score *= float(cur_score)
                    # print(f"[must exclude] {cur_score}, selected element: {selected_element}, required contents: {content}")
            elif "required_values" in target["required_contents"]:
                required_values = target["required_contents"][
                    "required_values"
                ]
                assert isinstance(required_values, list)
                if isinstance(selected_element, str):
                    selected_element = NumericEvaluator.str_2_int(
                        selected_element
                    )
                if selected_element is None:
                    score = 0.0
                else:
                    for value in required_values:
                        value_or = value.split(" |OR| ")
                        cur_score = any(
                            [
                                NumericEvaluator.compare_inequality(
                                    selected_element, value
                                )
                                for value in value_or
                            ]
                        )
                        score *= float(cur_score)
                        # print(f"[required values] {cur_score}, selected element: {selected_element}, required values: {value_or}")
            elif "fuzzy_match" in target["required_contents"]:
                targets = target["required_contents"]["fuzzy_match"]
                assert isinstance(targets, str)
                targets = targets.split(" |OR| ")
                for target in targets:
                    cur_score = max(
                        [
                            StringEvaluator.fuzzy_match(
                                ref=target,
                                pred=selected_element,
                                intent="NOT USED",
                            )
                        ]
                    )
                    score *= float(cur_score)
                    # print(f"[fuzzy match] {cur_score}, selected element: {selected_element}, required contents: {target}")
            else:
                raise ValueError(
                    f"Unknown required_contents: {target['required_contents'].keys()}"
                )

            if prev_page:
                page.close()
                page = prev_page
                prev_page = None

        return score

class PageImageEvaluator(Evaluator):
    """Check whether the answer is correct by querying a vision model."""

    def __init__(self, captioning_fn=None):
        if captioning_fn is None:
            raise ValueError("captioning_fn must be provided.")
        self.captioning_fn = captioning_fn
        # Default to 0.8 as the threshold for similarity to account for compression, resizing, etc
        # This might be too generous but we bias towards minimizing false negatives.
        self.ssim_threshold = 0.8

    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage | None = None
    ) -> float:
        with open(config_file, "r") as f:
            configs = json.load(f)

        for query in configs["eval"]["page_image_query"]:
            locator: str = query["eval_image_class"]
            target_url: str = query["eval_image_url"]
            if target_url.startswith("func"):
                func = target_url.split("func:")[1]
                func = func.replace("__last_url__", page.url)
                target_url = eval(func)

            # navigate to that url
            if target_url != "last":
                page.goto(target_url)
                time.sleep(3)  # TODO(jykoh): fix this hard-coded sleep

            # empty, use the full page
            if not locator.strip():
                images = page.get_by_role("img").all()
            # use JS to select the element
            elif locator.startswith("."):
                # Get all img children under the locator
                elements = page.query_selector_all(locator)
                images = []
                for element in elements:
                    is_img = element.evaluate(
                        'element => element.tagName === "IMG"'
                    )
                    if is_img:
                        images.append(element)
                    else:
                        images.extend(element.query_selector_all("img"))
            else:
                raise ValueError(f"Unknown locator: {locator}")

            if images == []:
                return 0.0

            all_image_pixels = []
            for image in images:
                try:
                    # Get image from URL.
                    image_url = image.get_attribute("src")
                    if not image_url.startswith(
                        ("http://", "https://", "www.")
                    ):
                        image_url = urljoin(page.url, image_url)
                    image = Image.open(
                        requests.get(image_url, stream=True).raw
                    )
                    all_image_pixels.append(image)
                except Exception as e:
                    print("[WARNING]: ", e)

            score = 1.0
            if all_image_pixels == []:
                return 0.0
            else:
                # Run the VQA eval on the image elements.
                eval_vqas = query.get("eval_vqa", [])
                assert (
                    len(eval_vqas) > 0 or "eval_fuzzy_image_match" in query
                ), "eval_vqa must have at least 2 questions or eval_fuzzy_image_match must be True"
                for qa in eval_vqas:
                    question, answer = qa["question"], qa["answer"]
                    prompt = f"Q: {question} A:"
                    pred_ans = self.captioning_fn(
                        all_image_pixels, [prompt] * len(all_image_pixels)
                    )
                    score *= float(
                        any(
                            [answer.lower() in ans.lower() for ans in pred_ans]
                        )
                    )

                if "eval_fuzzy_image_match" in query:
                    ssim_threshold = query.get(
                        "ssim_threshold", self.ssim_threshold
                    )
                    exact_match_imgs = query["eval_fuzzy_image_match"].split(
                        " |OR| "
                    )
                    all_exact_match_pixels = []

                    for exact_match_img in exact_match_imgs:
                        if exact_match_img.startswith("http"):
                            exact_match_pixels = Image.open(
                                requests.get(exact_match_img, stream=True).raw
                            )
                        else:
                            exact_match_pixels = Image.open(exact_match_img)
                        all_exact_match_pixels.append(exact_match_pixels)

                    # Check if any of the images on the page match
                    found_exact_match = False
                    for exact_match_pixels in all_exact_match_pixels:
                        for image_pixels in all_image_pixels:
                            ssim = get_image_ssim(
                                image_pixels, exact_match_pixels
                            )
                            if ssim > ssim_threshold:
                                found_exact_match = True
                                break
                    score *= float(found_exact_match)

        return score


class EvaluatorComb:
    def __init__(self, evaluators: list[Evaluator]) -> None:
        self.evaluators = evaluators

    @beartype
    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage,
        client: CDPSession | None,
    ) -> float:

        score = 1.0
        for evaluator in self.evaluators:
            cur_score = evaluator(trajectory, config_file, page)
            score *= cur_score

        return score

# @beartype
# def evaluator_router(
#     config_file: Path | str, captioning_fn=None
# ) -> EvaluatorComb:
    # with open(config_file, "r") as f:
    #     configs = json.load(f)
    # eval_types = configs["eval"]["eval_types"]
    # evaluators: list[Evaluator | EvaluatorPartial] = []

@beartype
def evaluator_router(eval_types: list[str], captioning_fn=None, model: str = "gpt-4o") -> EvaluatorComb:
    """Router to get the evaluator class"""

    evaluators: list[Evaluator] = []
    for eval_type in eval_types:
        match eval_type:
            case "string_match":
                evaluators.append(StringEvaluator(model=model))
            case "url_match":
                evaluators.append(URLExactEvaluator())
            case "program_html":
                evaluators.append(HTMLContentExactEvaluator())
            case "page_image_query":
                evaluators.append(PageImageEvaluator(captioning_fn=captioning_fn))
            case _:
                raise ValueError(f"eval_type {eval_type} is not supported")

    return EvaluatorComb(evaluators)
