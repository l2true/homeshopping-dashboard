;(function($,win){
	let scheduleSearch = function(){
		let cls = this;
		cls.deviceChecker = $('#MCDeviceChecker').data('devicechecker');
		cls.isApp = cls.deviceChecker.app;
		cls.keywordParam = gsCommon.getParam(location.href, "keyword");
		cls.searchLayer;
		cls.searchInput = document.getElementById("header-srch") || '';
		cls.headerInput = document.getElementById("header-srch") || '';
		cls.contentArea =  $('#main_area').size() == 0 ? '#cont_wrap' : '#main_area';
		cls.mseqFix = {"LIVE" : "-SC_PAGE", "ETC" : "-SC_PAGE_P"}
		cls.mseqObj = {
			'MAIN_ALARM_ON'		    : '-AR'		        // LIVE/DATA 방송알림 등록
			, 'MAIN_ALARM_OFF'		: '-AC'		        // LIVE/DATA 방송알림 해제
			, 'SHOPPY_ALARM_ON'     : '-PAR'            // SHOPPY 방송알림 등록
			, 'SHOPPY_ALARM_OFF'    : '-PAC'            // SHOPPY 방송알림 해제
			, 'LIVETALK'			: '-TALK' 	        // 라이브톡
			, 'DIRECT_ORDER'        : '-BUY'            // 구매하기
			, 'SUB_DIRECT_ORDER'    : '-SUB_BUY'        // 부상품 구매하기
			, 'MORE_OPEN'			: '-SUB_OPEN'       // 부상품 더보기 오픈
			, 'MORE_CLOSE'			: '-SUB_CLOSE'      // 부상품 더보기 닫기

			// 방송알림 등록 TOP 10
			// , 'WISH'                : '-AR_TOP-BZ'      // 찜
			, 'ALARM_ON'            : '-AR_TOP-AR'      // 방송알림 등록
			, 'ALARM_OFF'           : '-AR_TOP-AC'      // 방송알림 해제
			, 'ALL_SEARCH'          : '-ALL_SC'         // 검색결과 없는 경우 통합검색

			// TV상품 TOP 10
			// , 'TV_WISH'             : '-BZ'             // 찜
		}

		cls.init = function() {
			$(window).scrollTop(0);
			// 앱에서 페이지 초기 진입시 layer 자동 오픈
			if(cls.isApp && gsCommon.getParam(location.href, "gbn") == 'init') {
				cls.openLayer(cls.headerInput.value);
			}
			cls.setEvent();
		}

		cls.setEvent = function() {
			if(document.querySelector('#gs-md-srch-schedule .gs-srch-frm')){
				document.querySelector('#gs-md-srch-schedule .gs-srch-frm')
				.addEventListener('click', function(e){
					cls.openLayer(cls.headerInput.value);
				},false);
			}

			// 검색 input
			$('#keyword, #header-srch').keydown(function(e) {
				cls.viewDeleteBtn();
			}).off('keypress').on('keypress', function(e) {
				// enter 키 입력 시 검색결과 페이지 이동
				if(e.keyCode == 13){
					cls.clickSearchBtn(e);
				}
			}).focusin(function() {
				cls.viewDeleteBtn();
			});

			// 검색어 삭제 버튼
			$('#gs-md-srch-schedule .btn_del_srch, #cont_wrap .btn_del_srch').off('click').on('click', function(e){
				e.stopPropagation();
				cls.openLayer('');
			});

			// 돋보기 버튼 - 클릭 시 검색결과 페이지 이동
			$('#gs-md-srch-schedule .btn_srch, .srch-submit , #cont_wrap .btn_srch').off('click').on('click', function(e) {
				cls.clickSearchBtn(e);
			});

			// 편성표 검색 레이어 내 상품 방송알림 등록 버튼
			$('#gs-md-srch-schedule [name=btnBroadAlarm]').off('click').on('click', function(e) {
				e.stopPropagation();
				let broadType = $(this).closest('.prd-item').data('broadtype');
				let prdCd = $(this).closest('.prd-item').data('prdcd');
				let gbnParam = {
					alarmOn : 'ALARM_ON'
					, alarmOff : 'ALARM_OFF'
					, isSearchYn : 'Y'         // 편성표 검색에서 호출하는 경우 'Y'
				}

				if('S' == broadType) {
					// SHOPPY 방송 알림
					window.scheduleCommon.broadAlarmShoppy.call($(this), e, gbnParam);

					// 레이어 바깥 영역에도 같은 상품 존재하는 경우 방송 알림 on/off 처리
					let contentTarget = $(`${cls.contentArea} [name=btnSpBroadAlarm][data-prdcd=${prdCd}]`);
					window.scheduleCommon.setBroadAlarmOnOff(contentTarget);
				} else {
					// LIVE/DATA 방송 알림
					window.scheduleCommon.broadAlarmLiveAndData.call($(this), e, gbnParam);

					// 레이어 바깥 영역에도 같은 상품 존재하는 경우 방송 알림 on/off 처리
					let contentTarget = $(`${cls.contentArea} .prd-group.typeB .prd-item.card[data-prdcd=${prdCd}] [name=btnBroadAlarm]`)
					window.scheduleCommon.setBroadAlarmOnOff(contentTarget);
				}
			});

			// 전체 검색
			$('#btnSearchAll').off('click').on('click', function(e) {
				e.preventDefault();
				let params = {
					gbn : 'ALL_SEARCH'
				};
				let mseq = window.scheduleCommon.setMseq(params);
				location.href = `/search/searchSect.gs?tq=${cls.keywordParam}&mseq=${mseq}`;
			});

			// 찜버튼 설정
			cls.setWishButton();
		}

		// 레이어 닫기
		cls.closeLayer = function () {
			if (cls.isApp && cls.headerInput.value == '') {
				// 앱 : 웹뷰 닫기
				location.href = 'toapp://close';
			}
		}

		// 검색어 삭제 버튼 노출/비노출 처리
		cls.viewDeleteBtn = function() {
			let keyword = cls.checkKeyword();
			if (keyword != '') {
				// 검색어 삭제 버튼 노출
				$('#gs-md-srch-schedule [clear-val]').css('display', 'block');
			} else {
				// 검색어 삭제 버튼 비노출
				$('#gs-md-srch-schedule [clear-val]').css('display', 'none');
			}
		}

		// 검색 결과 페이지 노출
		cls.clickSearchBtn = function(e) {
			e.preventDefault();
			e.stopPropagation();
			let keyword = cls.checkKeyword();
			if (keyword != '') {
				document.location.href = `/main/broadSchedule/search.gs?keyword=${keyword}&isApp=${cls.isApp}`;
			} else {
				cls.searchInput.value = '';
				alert('검색어를 입력해 주세요.');
				return;
			}
		}

		cls.checkKeyword = function() {
			let keyword = $(cls.searchInput).val();
			if(keyword == '') keyword = $("#keyword").val();
			
			keyword = keyword.replace("<","");
			keyword = keyword.replace(">","");
			keyword = keyword.replace(/&/gi,"%26");
			keyword = keyword.replace(/\+/gi,"%2B");
			//공백제거
			keyword = keyword.replace(/(^\s*)|(\s*$)/g, "");
			return keyword;
		}

		// 찜 설정
		cls.setWishButton = function () {
			comWishButtom(cls.loginBeforeProc, cls.successAfterProc);
		};

		// 찜 전 이벤트 설정
		cls.loginBeforeProc = function () {
			// cls.setSessionStorage();
		};

		// 찜 후 이벤트 설정
		cls.successAfterProc = function (prdId) {
			// 효율코드 java에서 처리!
			// cls.removeSessionStorage();
			// let params = {
			// 	gbn : 'WISH'
			// };
			// gsCommon.sendClickTrac({ mseq : window.scheduleCommon.setMseq(params) });
		};

		// 레이어 오픈 이벤트
		cls.openLayer = function(keyword) {
			if(!document.querySelector('#srch-gate')) {
				return;
			}
			// ajax 호출을 레이어 컨텐츠를 노출했는지 여부 체크
			let target = document.querySelector('#srch-gate').innerHTML || '';
			if(!target) {
				let params = {
					isApp : cls.isApp
				}
				cls.callAjax('#srch-gate', '/main/broadSchedule/searchLayer.gs', params);
			}
			cls.setSearchLayer();
			$(cls.searchInput).val(keyword);
			cls.viewDeleteBtn();
		}

		// 편성표 검색 레이어 오픈 시 필요한 처리
		cls.setSearchLayer = function() {
			cls.searchLayer = new gs.modal('#gs-md-srch-schedule', {
				callbackClose : cls.closeLayer
			});
			cls.searchLayer.open();
			setTimeout(()=>{
				$("#keyword").focus();
			},100);
		}

		cls.callAjax = function( t, url, params ) {
			// ajax 실행 ~ 단순 예제 함수로 분리해도 무방
			let Loader;
			$.ajax ({
				url: url,
				type: 'get',
				data: params,

				beforeSend: function(){
					Loader = appendLoader( t, 'abs');
					DATA_STORE = '';
				},
				success: function( data ) {
					if (t == '#gs-main') {
						gs.scrollMove = false;
						$(window).scrollTop(gs.floatingY);
					}

					if (data) {
						$(t).html( data );
						setTimeout(()=>{
							// gs.scrollMove = true;
							cls.setEvent();
							let param = {
								// contentId : '#gs-md-srch-schedule'
								mseqFix : cls.mseqFix
								, mseqObj : cls.mseqObj
							};
							// window.scheduleCommon = new scheduleCommon(param);
							// window.scheduleCommon.init();
							// window.scheduleCommon.init(param);
							window.scheduleCommon.initData(param);
							window.scheduleCommon.init();
						},100);
					}
				},
				error: function( xhr, status, error) {
					console.log( xhr +' \n' + xhr.status +t +' 오류 발생!!');
					setTimeout(()=>{
						$(t).html(`<div class="empty-data full">
						<i class="gis-connection_signal"></i>
						<p class="ttl-base">네트워크 연결이 원활하지 않아요</p>
						<p class="sub">잠시 후 다시 연결을 시도해주세요</p>
					</div>`);
						$(window).scrollTop(gs.floatingY);
					},300);
				}
			});
		}
	}

	window.scheduleSearch = window.scheduleSearch || new scheduleSearch();
	window.scheduleSearch.init();

	let param = {
		// contentId : '#main_area'
		mseqFix : window.scheduleSearch.mseqFix
		, mseqObj : window.scheduleSearch.mseqObj
	};
	// window.scheduleCommon = new scheduleCommon(param);
	// window.scheduleCommon.init();
	// window.scheduleCommon.init(param);
	window.scheduleCommon.initData(param);
	window.scheduleCommon.init();
})(jQuery, window);
