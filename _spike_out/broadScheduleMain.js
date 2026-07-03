;(function($,win){ 
	/** 
	 * <pre>
	 * 방송편성표 컨트롤러 
	 * </pre>
	 */ 
	let broadSchedule = function(){
		let cls = this;

		/**
		 * 변수영역
		 */
		{
			/**
			 * <pre>데이터가 로딩중인지 여부</pre>
			 */
			cls.isLoadData = false;  
			/**
			 * <pre>
			 * 생방송 남은시간 처리 여부
			 * 히스토리백과 날짜변경시 생방송 남은시간 처리여부 판단
			 * </pre>
			 */
			cls.isOnAirCount = false;
			/**
			 * <pre>다음방송시간과 현재시간의 간격</pre>
			 */
			cls.timerDiffTimes = new Array();
			/**
			 * <pre>방송편성표 URL정보</pre>
			 */
			cls.broadScheduleUrl = '/main/broadSchedule';
			/**
			 * <pre>생방송남은시간 setTimeout</pre>
			 */
			cls.timerIntervals = new Array();
			/**
			 * <pre>방송상품리스트 CSS</pre>
			 */
			cls.broadContentsArea = '#broadSchedule';
			/**
			 * <pre>요일포맷</pre>
			 */
			cls.dayOfWeek = ['일','월','화','수','목','금','토'];
			/**
			 * <pre>방송타입</pre>
			 */
			cls.broadType = 'ALL';
			// 편성표 검색 유도 툴팁
			cls.broadSearchGuide;

			cls.commonMseqObj = {
				'MAIN_ALARM_ON'		    : '-AR'		        // LIVE/DATA 방송알림 등록
				, 'MAIN_ALARM_OFF'		: '-AC'		        // LIVE/DATA 방송알림 해제
				, 'SHOPPY_ALARM_ON'     : '-PAR'            // SHOPPY 방송알림 등록
				, 'SHOPPY_ALARM_OFF'    : '-PAC'            // SHOPPY 방송알림 해제
				, 'LIVETALK'			: '-TALK' 	        // 라이브톡
				, 'DIRECT_ORDER'        : '-BUY'            // 구매하기
				, 'SUB_DIRECT_ORDER'    : '-SUB_BUY'        // 부상품 구매하기
				, 'MORE_OPEN'			: '-SUB_OPEN'       // 부상품 더보기 오픈
				, 'MORE_CLOSE'			: '-SUB_CLOSE'      // 부상품 더보기 닫기
				, 'CHANNEL_INFO'        : '-INFO'           // 방송채널 안내 팝업
				, 'SEARCH_BTN'			: '-SC' 	        // 검색버튼
				, 'N_SWT_ALL'			: '-N_SWT-ALL'        // 전체 탭
				, 'N_SWT_LIVE'			: '-N_SWT-LIVE'       // LIVE 탭
				, 'N_SWT_DATA'			: '-N_SWT-MYSHOP'     // DATA 탭
				, 'N_SWT_SHOPPY'		: '-N_SWT-MLIVE'      // SHOPPY 탭
			}

			/**
			 * <pre>MSEQ 효율코드정의</pre>
			 */
			cls.allMseqFix = {"LIVE" : "-C_ALL", "ETC" : "-C_ALL_P"}
			cls.allMseqObj = {
				'DATE_TODAY'			: '-ALL-TODAY'// 달력 오늘
				, 'DATE_PRV'			: '-ALL-PD-' 	// 달력 이전
				, 'DATE_NEXT'			: '-ALL-ND-' 	// 달력이후
			}

			cls.liveMseqFix = {"LIVE" : "-C_LIVE", "ETC" : "-C_LIVE_P"}   // live 방송 여부에 따라 구분 할수 있어 제거 안함
			cls.liveMseqObj = {
				'DATE_TODAY'			: '-C_SCH-TODAY'    // 달력 오늘
				, 'DATE_PRV'			: '-C_SCH-PD-' 	    // 달력 이전
				, 'DATE_NEXT'			: '-C_SCH-ND-' 	    // 달력 이후
			}

			cls.dataMseqFix = {"LIVE" : "-C_MYSHOP", "ETC" : "-C_MYSHOP_P"}
			cls.dataMseqObj = {
				'DATE_TODAY'			: '-C_SCH_D-TODAY'  // 달력 오늘
				, 'DATE_PRV'			: '-C_SCH_D-PD-' 	// 달력 이전
				, 'DATE_NEXT'			: '-C_SCH_D-ND-' 	// 달력 이후
			}

			cls.shoppyMseqFix = {"LIVE" : "-C_MLIVE", "ETC" : "-C_MLIVE_P"}
			cls.shoppyMseqObj = {
				'DATE_TODAY'			: '-C_SCH_S-TODAY'  // 달력 오늘
				, 'DATE_PRV'			: '-C_SCH_S-PD-' 	// 달력 이전
				, 'DATE_NEXT'			: '-C_SCH_S-ND-' 	// 달력 이후
			}

			cls.liveIO = null; // 지금 방송가기 옵저버
		}

		/**
		 * 함수영역
		 */
		{
			/**
			 * <pre>
			 * 초기화
			 * </pre>
			 * @param isAjax ajax로딩여부
			 */
			cls.init = function(isAjax){
				let broadType = gsCommon.m_storage.getItem("broadSchedule.broadType");
				if('undefined' == typeof isAjax || 'Y' !=  isAjax){
					cls.broadType = (null != broadType && 'undefined' != broadType) ? broadType : 'ALL';
					// cls.timeLive.init();
					// LNB 틀고정
					cls.scheduleTab();
					// cls.moveToggle();
				}

				cls.setNextPrevMoreBtn();
				cls.createLoadingBar();
				cls.setEvent();
				cls.initMseq(cls.broadType);
                cls.openOnairSalePsblPrdArea();

				setTimeout(function(){
					// scheduleCommon.init();
					// scheduleCommon.setOnAirTimer();
					let param = {
						// contentId : '#main_area'
						mseqFix : cls.mseqFix
						, mseqObj : cls.mseqObj
						, broadType : cls.broadType
					};
					// window.scheduleCommon = scheduleCommon.init(param);
					// window.scheduleCommon.init();
					window.scheduleCommon.initData(param);
					window.scheduleCommon.init();

					gsCommon.m_storage.removeItem("broadSchedule.broadType");
					cls.channelInfoPopup();
					cls.goLivePrd();
					cls.clickBtnGoLive(isAjax);
					// 편성표 검색 유도 툴팁
					cls.broadSearchGuideTooltip();
				}, 500);
			}

			/**
			 * 쿠키값 저장
			 */
			cls.setCookie = function(key, value) {
				// 만료기간 설정 : 금일 23시 59분 59초까지
				const date = new Date();
				date.setHours(23, 59, 59, 999);
				const expires = `; expires=${date.toUTCString()}`;
				document.cookie = `${key}=${value}${expires}; path=/`;
			}

			/**
			 * 편성표 검색 유도 툴팁
			 * - 코너에 등록한 기간동안 1일 1회만 노출함
			 */
			cls.broadSearchGuideTooltip = function() {
				cls.broadSearchGuide = document.querySelector('#broadcastSchGuide');

				if(!cls.broadSearchGuide) {
					return;
				}
				if(gsCommon.getCookieValue("broadSearchGuideFlag") !== 'Y') {
					cls.broadSearchGuide.classList.add('on');
					cls.setCookie('broadSearchGuideFlag', 'Y')
				}

				// 편성표 검색 유도 툴팁 닫기 버튼
				cls.broadSearchGuide.querySelector('.close-btn')
					.addEventListener('click', function(e){
						cls.broadSearchGuide.classList.remove('on');
					});
			}

			/**
			 * 방송채널 안내 팝업
			 */
			cls.channelInfoPopup = function() {
				let btnChannelInfo = document.querySelector('#btn-channel-info');
				if(btnChannelInfo) {
					cls.mdChennel = new gs.modal('#md-broad-channel', {
						callbackCloseEnd: function(t){
							// console.log('close end'); // 완전히 닫히고 실행
						},
					});

					document.querySelector('#btn-channel-info')
						.addEventListener('click', function(){
							cls.mdChennel.open();
							let param = {};
							param.gbn = 'CHANNEL_INFO';
							gsCommon.sendClickTrac({mseq: window.scheduleCommon.setMseq(param)});
						});
				}
			}

			// 방송 스케줄 탭
			cls.scheduleTab = function() {
				setTimeout(function() {
					// 틀고정
					let scheduleFix = new gs.sticky('.prd-schedule-lnb', {
						effect: 'fixed'
					});

					// LNB 날짜 Tab
					let tabDate = new gs.tab('.prd-schedule-navi ', {
						tabPosition: 1,
						dynamicActive: true,
						callbackClick: function (el) {
							cls.clickDate(el);
						}
					});

					// LNB 방송 Tab
					let tabBroacast = new gs.tab('#nav-schedule-store', {
						dynamicActive: true,
						callbackClick: function(t, b){
							document.querySelector('.flex-items-wrap').dataset.view =  t.dataset.view;
							cls.moveToggle(t);
							// cls.goLivePrd( t.dataset.view );
						}
					});
				}, 10);
			}

			// 라이브 상품으로 이동
			cls.goLivePrd = function() {
				let onAir, hasOnAir;
				let livePrds = document.querySelectorAll('.prd-group.onair');

				livePrds.forEach((el)=>{
					if (el.clientHeight > 10 && !hasOnAir ){
						onAir = el;
						hasOnAir = true;
						return false;
					}
				});
				if ( livePrds.length ) {
					// 방송중인 상품 있으면 해당 상품으로 이동
					gs.tabMoveEvent( onAir );
				} else {
					// 방송중인 상품 없으면 상단으로 이동
					// let daySchedule = document.querySelector('#setDateArea');
					let daySchedule = document.querySelector(cls.broadContentsArea);
					gs.tabMoveEvent( daySchedule );
				}
			}

			cls.clickDate = function(el) {
				let today = $('.prd-schedule-navi a[data-todayyn=Y]').data('brddate');
				let targetDate = $(el).data('brddate');
				let nowDate = $('.prd-schedule-navi .day-item.on').data('brddate');
				let url = win.broadSchedule.broadScheduleUrl;
				let param = {};
				param.broadType = win.broadSchedule.broadType;
				param.startDate = ''.concat(targetDate);
				win.broadSchedule.loadScheduleData(url, param);

				const date1_year = parseInt(String(targetDate).substring(0, 4))
				const date1_month = parseInt(String(targetDate).substring(4, 6)) - 1
				const date1_day = parseInt(String(targetDate).substring(6, 8))

				const date2_year = parseInt(String(today).substring(0, 4))
				const date2_month = parseInt(String(today).substring(4, 6)) - 1
				const date2_day = parseInt(String(today).substring(6, 8))

				// 날짜 문자열을 Date 객체로 변환
				const date1 = new Date(date1_year, date1_month, date1_day);
				const date2 = new Date(date2_year, date2_month, date2_day);

				// 두 날짜의 차이 계산 (밀리초 단위로 계산되므로 일 단위로 변환)
				const differenceInMilliseconds = date1 - date2;
				let interval = differenceInMilliseconds / (1000 * 60 * 60 * 24);

				let mseqParams = {};
				if(interval > 0){
					mseqParams.gbn = 'DATE_NEXT';
					mseqParams.idx = Math.abs(interval);
				}else if(interval < 0){
					mseqParams.gbn = 'DATE_PRV';
					mseqParams.idx = Math.abs(interval);
				}else if(interval == 0){
					mseqParams.gbn = 'DATE_TODAY';
				}
				gsCommon.sendClickTrac({ mseq : window.scheduleCommon.setMseq(mseqParams)});
			}

            /**
             * [HANGBOT-31282] 방송중 구매가능 상품 - 관련 상품 영역 펼쳐진 형태로 노출
             * 방송중 구매가능 상품 중에서도 생방송 30분 전/후 버튼 색상 red인 케이스는 제외
             */
            cls.openOnairSalePsblPrdArea = function () {
                let objMoreViewBtn = document.querySelectorAll('button[data-moreviewyn="Y"]');
	            if(objMoreViewBtn.length > 0) {
	                objMoreViewBtn.forEach(function(el) {
		                el.click();
	                });
	            }
            }

			/**
			 * <pre>
			 * 방송유형에 따른 효율 코드 초기화
			 * 20220106 SHOPPY 추가 - [HANGBOT-27576]
			 * </pre>
			 */
			cls.initMseq = function(broadType){
				let targetMseq;
				if('ALL' == broadType) {
					cls.mseqFix = cls.allMseqFix;
					targetMseq = cls.allMseqObj;
				}else if('DATA' == broadType){
					cls.mseqFix = cls.dataMseqFix;
					targetMseq = cls.dataMseqObj;
				}else if('LIVE' == broadType){
					cls.mseqFix = cls.liveMseqFix;
					targetMseq = cls.liveMseqObj;
				}else{
					//20220106 SHOPPY 추가 - [HANGBOT-27576]
					// 위 작업에 안되어 있어서 GRIT-75207에서 다시 작업
					cls.mseqFix = cls.shoppyMseqFix;
					targetMseq = cls.shoppyMseqObj;
				}
				cls.mseqObj = Object.assign(cls.commonMseqObj, targetMseq);
			}

			/**
			 * <pre>
			 * TODO 이전, 다음 날짜의 편성표 더보기 정보
			 * </pre>
			 */
			cls.setNextPrevMoreBtn = function(){
				// 선택된 날짜 css
				let timeLiveSwiperCssOfOnair = $('.prd-schedule-navi .day-item.on');
				let tdate = $(timeLiveSwiperCssOfOnair).data('brddate');
				if('undefined' != typeof tdate && 8 == ''.concat(tdate).length){
					tdate = ''.concat(tdate);
					let year = Number(tdate.substring(0,4));
					let month = Number(tdate.substring(4,6)) - 1;
					let day = Number(tdate.substring(6,8));
					let tm = new Date(year, month, day);

					// 이전날짜 편성표 더보기
					if($(timeLiveSwiperCssOfOnair).prev().data('brddate')){
						let dPrev = new Date(tm.getTime() - (1000 * 3600 * 24 * 1));
						cls.setNextPrevMoreBtnDetail('prev', dPrev);
					}
					// 다음날짜 편성표 더보기
					if($(timeLiveSwiperCssOfOnair).next().data('brddate')){
						let dNext = new Date(tm.getTime() + (1000 * 3600 * 24 * 1));
						cls.setNextPrevMoreBtnDetail('next', dNext);
					}
				}
			}


			/**
			 * <pre>
			 * 이전, 다음 날짜의 편성표 더보기 정보 상세
			 * </pre>
			 * @param gbn 구분 (next : 다음날짜, prev : 이전날짜)
			 * @param date 대상날짜 new Date()
			 */
			cls.setNextPrevMoreBtnDetail = function(gbn, date){
				let timeLiveSwiperCssOfOnair = $('.prd-schedule-navi .day-item.on');
				let contentCssClass = (`#main_area #${gbn}`);
				let brdDate = 'prev' == gbn ? $(timeLiveSwiperCssOfOnair).prev().data('brddate') : $(timeLiveSwiperCssOfOnair).next().data('brddate');

				$(contentCssClass).attr("data-brddate",brdDate);
				$(`${contentCssClass} strong`).html(`${date.getMonth() + 1}. ${date.getDate()}.(${cls.dayOfWeek[date.getDay()]}) 편성보기`);
				$(contentCssClass).show();
			}

			/**
			 * <pre>
			 * 히스토리백 관련 처리
			 * </pre>
			 */
			cls.checkHistoryBack = function(){
				setTimeout(function() {
					let param = {
						// contentId : '#main_area'
						mseqFix : cls.mseqFix
						, mseqObj : cls.mseqObj
						, broadType : cls.broadType
					};
					// window.scheduleCommon = new scheduleCommon(param);
					// window.scheduleCommon.init();
					window.scheduleCommon.initData(param);
					window.scheduleCommon.init();
				}, 500);

				let scrollY = gsCommon.getStorageOfPageCache("broadSchedule.scrollY");

                if(scrollY){
					cls.broadType = gsCommon.getStorageOfPageCache("broadSchedule.broadType");
					cls.initMseq(cls.broadType);

					$('#main_area').html(gsCommon.getStorageOfPageCache("broadSchedule.contents"));
					$(window).scrollTop(scrollY);
					cls.removeSessionStorage();

					cls.isOnAirCount = true;
					// cls.timeLive.init();
	                // let targetToggle = document.querySelector(`#nav-schedule-store .a-toggle[data-type="${cls.broadType}"]`);
					// cls.moveToggle(targetToggle);
					cls.setEvent();
					setTimeout(function(){
						cls.scheduleTab();
						window.scheduleCommon.setOnAirTimer();
						cls.procScrollMove('Y');
					}, 500);
					$('#moreDiv').hide();
				}
			}

			/**
			 * 전체 / LIVE / DATA / SHOPPY 토글 버튼
			 */
			cls.moveToggle = function(el){
				gs.scrollMove = false;
				cls.broadType = el.dataset.type;

				let brddate = $('.prd-schedule-navi .day-item.on').data('brddate');
				let url = cls.broadScheduleUrl;
				let param = {};
				param.broadType = cls.broadType;
				param.startDate = brddate;
				param.gbn = el.dataset.mseq;
				cls.initMseq(cls.broadType);
				window.scrollTo(0, gs.floatingY);
				cls.loadScheduleData(url, param);
				gsCommon.sendClickTrac({mseq: window.scheduleCommon.setMseq(param)});
			}

			/**
			 * <pre>
			 * 이벤트설정
			 * </pre>
			 */
			cls.setEvent = function(){
				/**
				 * 이전, 다음날짜이동 버튼 이벤트
				 */
				$(`${cls.broadContentsArea} .set-schedule`).off('click').on('click', function(e){
					e.preventDefault();
					let selectedDate = $(this).data('brddate');
					let scheduleDate = $(`.prd-schedule-navi .day-item[data-brddate='${selectedDate}']`);
					scheduleDate.trigger('click');
				});

			    /**
			     * 상품상세 MSEQ 처리
			     */
			    // $(".prd-item .prd-link").off('click').on('click', function(e) {
				// 	console.log('prdprd')
				//     cls.setSessionStorage();
			    // });

			    /**
			     * 20220106 SHOPPY 추가 - [HANGBOT-27576] - SHOPPY 탭 - historyback
			     */
			    $("section#broadSchedule a.bnr-link").off('click').on('click', function(e) {
				    cls.setSessionStorage();
			    });

			    //무판매 상품 상품명 이동 시
			    $("#nonSalePrd a").off('click').on('click', function(e){
				    cls.setSessionStorage();
			    });

			    /**
			     * 생방송 동영상 MSEQ 처리
			     */
				$('.prd-item .badge-vod,.prd-item .badge-txt').off('click').on('click', function(e) {
					cls.setSessionStorage();
					gsCommon.goLink($(this).data("url"));
				});

				/**
			     * /20220106 SHOPPY 추가 - [HANGBOT-27576] - SHOPPY 탭
			     * 오늘 편성정보 보기
			     */
				$('article.prd-schedule-set.no-data button').off('click').on('click',function(e){
					let brddate = moment().format('YYYYMMDD')
					let $timelive = $(`.prd-schedule-navi .day-item[data-brddate='${brddate}']`);
					let url = cls.broadScheduleUrl;
					let param = {};
					param.startDate = ''.concat(brddate);
					param.broadType = cls.broadType;

					$('.day-item.today').click();
				});

				// 편성표 검색 버튼 이벤트
				$('#btn-broad-srch').off('click').on('click', function(e) {
					e.preventDefault();

					// 편성표 검색 유도 툴팁 존재하는 경우 툴팁 닫기
					if(cls.broadSearchGuide) {
						cls.broadSearchGuide.querySelector('.close-btn').click();
					}

					scheduleSearch.searchInput = document.getElementById("keyword");
					scheduleSearch.openLayer();
					let param = {};
					param.gbn = 'SEARCH_BTN';
					gsCommon.sendClickTrac({mseq: window.scheduleCommon.setMseq(param)});
				});
			}

			/**
			 * <pre>
			 * 세션스토리지 설정
			 * </pre>
			 */
			cls.setSessionStorage = function(){
				window.scheduleCommon.setSessionStorage();
				gsCommon.setStorageUsingCache('broadSchedule.broadType', cls.broadType);
			}

			/**
			 * <pre>
			 * 세션스토리지 제거
			 * </pre>
			 */
			cls.removeSessionStorage = function(){
				window.scheduleCommon.removeSessionStorage();
				gsCommon.removeStorageOfCurrentPage("broadSchedule.broadType");
			}

			/**
			 * <pre>
			 * 편성데이터를 ajax로 가져옴
			 * </pre>
			 * @param url 링크경로
			 * @param param json 포맷의 파라메터정보
			 */
			cls.loadScheduleData = function(url, param){
				if(!cls.isLoadData){
					// 성공시 데이터 처리
					let sCallback = function(data){
						cls.isOnAirCount = false;
						// 리스트
						let $t = $('<div></div>').attr("id","ajaxContents").html(data);
						let $broadSchedule = $t.find(cls.broadContentsArea);
						$(cls.broadContentsArea).html($broadSchedule.html());
						cls.init("Y");

						try {
							setTimeout(function () {
								gs.scrollMove = true; // gs.scrollMove 활성 반드시 필요 !!!
							}, 75);
						} catch (e) {
						}
					}

					// 데이터 로딩중 처리
					let bCallback = function(){
						cls.createLoadingBar();
						cls.isLoadData = true;
						$('.loading_cont_abs').show();
					}

					// 데이터 로딩 완료시 처리
					let cCallback = function(){
						cls.isLoadData = false;
						$('.loading_cont_abs').hide();
					}

					if('undefined' != typeof param.startDate){
						url += '/'.concat(param.startDate);
					}

					gsCommon.ajaxCall('get', url, param, sCallback, null, bCallback, cCallback);
				}
			}

			/**
			 * <pre>
			 * 현재날짜정보를 가져온다
			 * yyyyMMdd
			 * </pre>
			 */
			cls.getCurrentDate = function(){
				let date = new Date();
				let strDate = [];
				strDate.push(date.getFullYear());
				strDate.push('0'.concat(date.getMonth() + 1).substring('0'.concat(date.getMonth() + 1).length-2));
				strDate.push('0'.concat(date.getDate()).substring('0'.concat(date.getDate()).length-2));

				return strDate.join('');
			}

			/**
			 * <pre>
			 * 해당 날짜가 현재인지 여부
			 * </pre>
			 *
			 * @param targetDate yyyyMMdd 비교대상 날짜
			 */
			cls.isToday = function(targetDate){
				return cls.getCurrentDate() == targetDate;
			}

			/**
			 * <pre>
			 * 스크롤 이동시 처리
			 * </pre>
			 * @param flag 'Y' or 'N' 오른쪽 Swper 타임라인 강제이동여부
			 */
			cls.procScrollMove = function(flag){
				let $target;
				// 편성라인 상단 체크 위치 단말의 1/3 지점
				let topFixArea = $('header').offset().top + $('.tvshop-day-wrap').height() + $('header').height() + cls.getMoveHeight();
//				$('.tvshop-onair-item').each(function(idx){
				$('.live-item > .inr').each(function(idx){
					if($(this).offset().top < topFixArea){
						$target = $(this);
					}
					return;
				});
			}

			/**
			 * <pre>
			 * 화면의 컨텐츠 영역 1/3 지점 높이값
			 * </pre>
			 */
			cls.getMoveHeight = function(){
				return (window.screen.availHeight - $('header').height() - $('.tvshop-day-wrap').height() - $('.quick_link_area').height()) / 3;
			}

			/**
			 * <pre>
			 * 로딩바 생성
			 * </pre>
			 */
			cls.createLoadingBar = function(){
				// 2016-05-17 로딩바 독립사용 가능
				if($('.loading_cont_abs').size() == 0){
					let $loadBar = $("<div class='loading_cont_abs'><span class='loading15'></span></div>");
					$('body').append($loadBar);
					$loadBar.hide();
				}
			}

			// 지금 방송 버튼 클릭 이벤트
			cls.clickBtnGoLive = function(isAjax) {
				let btnMoveLive = document.querySelector('#go-live');
				if(btnMoveLive){
					if('Y' !== isAjax){
						btnMoveLive.addEventListener('click', function(){
							// let targetDate = $('.prd-schedule-navi .day-item.on').data('brddate');
							// if (cls.isToday(targetDate)) {
							// 	// 오늘 날짜인 경우 방송중인 상품으로 스크롤만 이동
							// 	cls.goLivePrd();
							// } else {
							// 오늘 날짜가 아닌 경우 오늘 날짜로 변경
							$('.day-item.today').click();
							// }
						});
						//옵저버 세팅
						// 리이브 방송이 아닐 경우 버튼 노출
						let liveOpitons = {
								rootMargin: '0px 0px 300px',
								threshold: 1
							},
							entryLive = [], outLive = [], deduplicationLive = [];
						cls.liveIO = new IntersectionObserver((entries) => {
							// ( 버튼 애니메이션 때문에 ) 전체 라이브 상품 여러개라 연속성 체크 필요
							entries.forEach((entry) => {
								if (entry.isIntersecting) {
									entryLive.push(entry.target);
									deduplicationLive = Array.from(new Set(entryLive));
									entryLive = deduplicationLive;
								} else {
									outLive = entryLive.filter((el)=> { return el != entry.target });
									entryLive = outLive;
								}
							});

							if ( entryLive.length>0) {
								btnMoveLive.classList.add('hidden2');
							} else {
								btnMoveLive.classList.remove('hidden2');
							}
						}, liveOpitons);
					}

					let livePrds = document.querySelectorAll('.prd-group.onair');

					if(livePrds){
						// 라이브 타겟 요소 관찰 시작
						livePrds.forEach((el) => {
							cls.liveIO.observe(el);
						});
					}
				}
			}

		}
		return cls;
	}
	window.broadSchedule = window.broadSchedule || new broadSchedule();
})(jQuery, window);
